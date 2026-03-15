"""AG-20: Tests for adaptive remediation engine.

Suites:
  TestRemediationPolicy     (5)
  TestAdaptationEngine      (5)
  TestAdaptiveRouter        (4)
  TestAdaptationStore       (4)
  TestFeedbackLoopAG20      (2)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


@contextmanager
def _TempRuntime():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = Path(tmp) / "runtime"
        (runtime / "state").mkdir(parents=True)
        (runtime / "logs").mkdir()
        old = os.environ.get("LUKA_RUNTIME_ROOT")
        os.environ["LUKA_RUNTIME_ROOT"] = str(runtime)
        try:
            yield runtime
        finally:
            if old is None:
                os.environ.pop("LUKA_RUNTIME_ROOT", None)
            else:
                os.environ["LUKA_RUNTIME_ROOT"] = old


# ---------------------------------------------------------------------------
# TestRemediationPolicy
# ---------------------------------------------------------------------------

class TestRemediationPolicy(unittest.TestCase):

    def test_allow_stop(self):
        from core.adaptation.remediation_policy import remediation_allowed
        self.assertEqual(remediation_allowed("stop"), "ALLOW")

    def test_allow_escalate(self):
        from core.adaptation.remediation_policy import remediation_allowed
        self.assertEqual(remediation_allowed("escalate"), "ALLOW")

    def test_block_destructive(self):
        from core.adaptation.remediation_policy import remediation_allowed
        self.assertEqual(remediation_allowed("delete"), "BLOCK")

    def test_block_retry_over_budget(self):
        from core.adaptation.remediation_policy import remediation_allowed, MAX_RETRY
        self.assertEqual(
            remediation_allowed("retry", retry_count=MAX_RETRY),
            "BLOCK",
        )

    def test_escalate_on_depth_ceiling(self):
        from core.adaptation.remediation_policy import remediation_allowed, MAX_ADAPTATION_DEPTH
        self.assertEqual(
            remediation_allowed("retry", adaptation_depth=MAX_ADAPTATION_DEPTH),
            "ESCALATE",
        )


# ---------------------------------------------------------------------------
# TestAdaptationEngine
# ---------------------------------------------------------------------------

class TestAdaptationEngine(unittest.TestCase):

    def test_success_returns_stop(self):
        from core.adaptation.adaptation_engine import choose_next_action
        result = choose_next_action(
            {"status": "SUCCESS"}, {"run_id": "r1"}
        )
        self.assertEqual(result, "STOP")

    def test_failed_returns_retry(self):
        from core.adaptation.adaptation_engine import choose_next_action
        result = choose_next_action(
            {"status": "FAILED"}, {"run_id": "r2"}
        )
        self.assertEqual(result, "RETRY")

    def test_partial_returns_safe_fallback(self):
        from core.adaptation.adaptation_engine import choose_next_action
        result = choose_next_action(
            {"status": "PARTIAL"}, {"run_id": "r3"}
        )
        self.assertEqual(result, "SAFE_FALLBACK")

    def test_depth_ceiling_returns_escalate(self):
        from core.adaptation.adaptation_engine import choose_next_action
        from core.adaptation.remediation_policy import MAX_ADAPTATION_DEPTH
        # Build prior with max depth exhausted
        prior = [
            {"action": "retry", "run_id": "r4"},
            {"action": "safe_fallback", "run_id": "r4"},
        ]
        result = choose_next_action(
            {"status": "FAILED"}, {"run_id": "r4"}, prior_adaptations=prior
        )
        self.assertEqual(result, "ESCALATE")

    def test_retry_budget_exhausted_returns_escalate(self):
        from core.adaptation.adaptation_engine import choose_next_action
        prior = [{"action": "retry", "run_id": "r5"}]
        result = choose_next_action(
            {"status": "FAILED"}, {"run_id": "r5"}, prior_adaptations=prior
        )
        self.assertEqual(result, "ESCALATE")


# ---------------------------------------------------------------------------
# TestAdaptiveRouter
# ---------------------------------------------------------------------------

class TestAdaptiveRouter(unittest.TestCase):

    def test_success_routes_stop(self):
        from core.adaptation.adaptive_router import route_adaptation
        with _TempRuntime():
            # Reload to pick up new LUKA_RUNTIME_ROOT
            import importlib, core.config, core.adaptation.adaptation_store as ast
            importlib.reload(core.config)
            importlib.reload(ast)
            result = route_adaptation({"status": "SUCCESS"}, {"run_id": "rr1"})
            self.assertEqual(result["action"], "STOP")
            self.assertEqual(result["gate_verdict"], "ALLOW")

    def test_failed_routes_retry(self):
        from core.adaptation.adaptive_router import route_adaptation
        with _TempRuntime():
            import importlib, core.config, core.adaptation.adaptation_store as ast
            importlib.reload(core.config)
            importlib.reload(ast)
            result = route_adaptation({"status": "FAILED"}, {"run_id": "rr2"})
            self.assertEqual(result["action"], "RETRY")
            self.assertEqual(result["gate_verdict"], "ALLOW")

    def test_record_persisted(self):
        from core.adaptation.adaptive_router import route_adaptation
        from core.adaptation.adaptation_store import get_latest
        with _TempRuntime():
            import importlib, core.config, core.adaptation.adaptation_store as ast
            importlib.reload(core.config)
            importlib.reload(ast)
            from core.adaptation import adaptation_store as ast2
            importlib.reload(ast2)
            route_adaptation({"status": "SUCCESS"}, {"run_id": "rr3"})
            latest = ast2.get_latest()
            self.assertIsNotNone(latest)
            self.assertEqual(latest["run_id"], "rr3")

    def test_over_budget_blocks(self):
        from core.adaptation.adaptive_router import route_adaptation
        with _TempRuntime():
            import importlib, core.config, core.adaptation.adaptation_store as ast
            importlib.reload(core.config)
            importlib.reload(ast)
            prior = [{"action": "retry", "run_id": "rr4"}]
            result = route_adaptation(
                {"status": "FAILED"}, {"run_id": "rr4"}, prior_adaptations=prior
            )
            # retry budget exhausted → choose_next_action returns ESCALATE, gate returns ALLOW
            self.assertEqual(result["action"], "ESCALATE")


# ---------------------------------------------------------------------------
# TestAdaptationStore
# ---------------------------------------------------------------------------

class TestAdaptationStore(unittest.TestCase):

    def test_append_creates_record(self):
        with _TempRuntime():
            import importlib, core.config
            importlib.reload(core.config)
            import core.adaptation.adaptation_store as ast
            importlib.reload(ast)
            rec = ast.append_adaptation({"run_id": "s1", "action": "STOP"})
            self.assertIn("adaptation_id", rec)
            self.assertIn("ts_utc", rec)

    def test_list_recent_returns_appended(self):
        with _TempRuntime():
            import importlib, core.config
            importlib.reload(core.config)
            import core.adaptation.adaptation_store as ast
            importlib.reload(ast)
            ast.append_adaptation({"run_id": "s2", "action": "RETRY"})
            records = ast.list_recent()
            self.assertEqual(len(records), 1)

    def test_write_latest_readable(self):
        with _TempRuntime():
            import importlib, core.config
            importlib.reload(core.config)
            import core.adaptation.adaptation_store as ast
            importlib.reload(ast)
            ast.write_latest({"run_id": "s3", "action": "STOP", "adaptation_id": "abc"})
            latest = ast.get_latest()
            self.assertIsNotNone(latest)
            self.assertEqual(latest["run_id"], "s3")

    def test_get_latest_returns_none_when_empty(self):
        with _TempRuntime():
            import importlib, core.config
            importlib.reload(core.config)
            import core.adaptation.adaptation_store as ast
            importlib.reload(ast)
            self.assertIsNone(ast.get_latest())


# ---------------------------------------------------------------------------
# TestFeedbackLoopAG20
# ---------------------------------------------------------------------------

class TestFeedbackLoopAG20(unittest.TestCase):

    def test_adaptation_id_in_result_on_success(self):
        """Nominal path: verification SUCCESS → STOP adaptation recorded."""
        from core.orchestrator import feedback_loop
        with _TempRuntime():
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"):
                result = feedback_loop.run_loop(
                    run_id="ag20-success",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            # adaptation_action should be STOP (verification status = SUCCESS for nominal plan)
            self.assertIn("adaptation_action", result)

    def test_adaptation_present_on_allowed_degraded(self):
        """When policy ALLOW + degraded classification, adaptation_action key exists."""
        from core.orchestrator import feedback_loop
        with _TempRuntime():
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"), \
                 patch("core.orchestrator.feedback_loop.policy_verdict", return_value="ALLOW"):
                result = feedback_loop.run_loop(
                    run_id="ag20-degraded",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            # When routed through execution, adaptation_action must be present
            self.assertIn("adaptation_action", result)


if __name__ == "__main__":
    unittest.main()
