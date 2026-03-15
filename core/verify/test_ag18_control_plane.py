"""AG-18 control plane verification tests.

Covers spec §14:
  test_decision_log_append
  test_policy_allow / test_policy_block / test_policy_escalate
  test_router_dispatch / test_router_block / test_router_escalate
  end-to-end: run → interpretation → decision → policy → router
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# --- path setup ----------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


class _TempRuntime:
    """Context manager: sets LUKA_RUNTIME_ROOT to a fresh temp directory."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = os.environ.get("LUKA_RUNTIME_ROOT")
        os.environ["LUKA_RUNTIME_ROOT"] = self._tmp.name
        return Path(self._tmp.name)

    def __exit__(self, *_):
        if self._orig is None:
            os.environ.pop("LUKA_RUNTIME_ROOT", None)
        else:
            os.environ["LUKA_RUNTIME_ROOT"] = self._orig
        self._tmp.cleanup()


# =========================================================================
# § 1 — Decision Persistence
# =========================================================================

class TestDecisionLogAppend(unittest.TestCase):

    def test_decision_log_append(self):
        """decision_log.jsonl must accept multiple append calls."""
        from core.decision.models import DecisionRecord
        # Reload decision_store so it picks up the patched env
        import importlib
        import core.decision.decision_store as ds_mod
        importlib.reload(ds_mod)
        from core.decision import decision_store as ds

        with _TempRuntime() as rt:
            importlib.reload(ds_mod)
            r1 = DecisionRecord.make(source_run_id="run1", classification="nominal",
                                     action="NO_ACTION", confidence=0.9)
            r2 = DecisionRecord.make(source_run_id="run2", classification="drift_detected",
                                     action="QUARANTINE", confidence=0.7)
            ds_mod.append_decision(r1)
            ds_mod.append_decision(r2)

            log_path = rt / "state" / "decision_log.jsonl"
            self.assertTrue(log_path.exists(), "decision_log.jsonl must exist")
            lines = [l for l in log_path.read_text().splitlines() if l.strip()]
            self.assertEqual(len(lines), 2, "must have 2 appended records")
            first = json.loads(lines[0])
            self.assertEqual(first["source_run_id"], "run1")

    def test_decision_latest_atomic(self):
        """decision_latest.json must be atomically overwritten."""
        from core.decision.models import DecisionRecord
        import importlib
        import core.decision.decision_store as ds_mod

        with _TempRuntime() as rt:
            importlib.reload(ds_mod)
            r1 = DecisionRecord.make(source_run_id="run1", classification="nominal",
                                     action="NO_ACTION", confidence=0.9)
            r2 = DecisionRecord.make(source_run_id="run2", classification="nominal",
                                     action="NO_ACTION", confidence=0.8)
            ds_mod.write_latest(r1)
            ds_mod.write_latest(r2)

            latest_path = rt / "state" / "decision_latest.json"
            self.assertTrue(latest_path.exists())
            data = json.loads(latest_path.read_text())
            self.assertEqual(data["source_run_id"], "run2", "latest must be overwritten")

    def test_get_latest_returns_none_when_missing(self):
        import importlib
        import core.decision.decision_store as ds_mod
        with _TempRuntime():
            importlib.reload(ds_mod)
            self.assertIsNone(ds_mod.get_latest())

    def test_list_recent_respects_limit(self):
        from core.decision.models import DecisionRecord
        import importlib
        import core.decision.decision_store as ds_mod
        with _TempRuntime():
            importlib.reload(ds_mod)
            for i in range(10):
                r = DecisionRecord.make(source_run_id=f"run{i}", classification="nominal",
                                        action="NO_ACTION", confidence=0.9)
                ds_mod.append_decision(r)
            recent = ds_mod.list_recent(limit=3)
            self.assertEqual(len(recent), 3)
            self.assertEqual(recent[-1]["source_run_id"], "run9")


# =========================================================================
# § 2 — Policy Gate
# =========================================================================

class TestPolicyGate(unittest.TestCase):

    def _make(self, action, confidence, source_run_id="test-run"):
        from core.decision.models import DecisionRecord
        return DecisionRecord.make(source_run_id=source_run_id, classification="test",
                                   action=action, confidence=confidence)

    def test_policy_allow_nominal(self):
        from core.policy.policy_gate import policy_verdict
        r = self._make("NO_ACTION", 0.9)
        self.assertEqual(policy_verdict(r), "ALLOW")

    def test_policy_allow_retry(self):
        from core.policy.policy_gate import policy_verdict
        r = self._make("retry", 0.9)
        self.assertEqual(policy_verdict(r), "ALLOW")

    def test_policy_block_destructive(self):
        from core.policy.policy_gate import policy_verdict
        for action in ("delete", "purge", "wipe", "kill"):
            r = self._make(action, 0.9)
            self.assertEqual(policy_verdict(r), "BLOCK", f"expected BLOCK for {action}")

    def test_policy_escalate_low_confidence(self):
        from core.policy.policy_gate import policy_verdict
        r = self._make("retry", 0.2)
        self.assertEqual(policy_verdict(r), "ESCALATE")

    def test_policy_escalate_unknown_action(self):
        from core.policy.policy_gate import policy_verdict
        r = self._make("unknown_future_op", 0.9)
        self.assertEqual(policy_verdict(r), "ESCALATE")

    def test_policy_block_retry_exceeded(self):
        from core.policy.policy_gate import policy_verdict
        from core.decision.models import DecisionRecord
        r = DecisionRecord.make(source_run_id="same-run", classification="drift",
                                action="retry", confidence=0.9)
        # One prior retry for the same run → exceeds MAX_RETRY_COUNT=1
        prior = [{"action": "retry", "source_run_id": "same-run"}]
        self.assertEqual(policy_verdict(r, prior_decisions=prior), "BLOCK")


# =========================================================================
# § 3 — Feedback Router
# =========================================================================

class TestFeedbackRouter(unittest.TestCase):

    def _make_decision(self, action="retry", confidence=0.9, source_run_id="test-run"):
        from core.decision.models import DecisionRecord
        return DecisionRecord.make(source_run_id=source_run_id, classification="nominal",
                                   action=action, confidence=confidence)

    def test_router_escalate(self):
        """ESCALATE verdict must write to operator_inbox."""
        from core.orchestrator.feedback_router import route
        import importlib
        import core.decision.decision_store as ds_mod

        with _TempRuntime() as rt:
            importlib.reload(ds_mod)
            d = self._make_decision(action="QUARANTINE")
            result = route("ESCALATE", d)
            self.assertEqual(result["routed_to"], "operator_queue")
            inbox = rt / "state" / "operator_inbox.jsonl"
            self.assertTrue(inbox.exists(), "operator_inbox.jsonl must exist after escalate")
            lines = [l for l in inbox.read_text().splitlines() if l.strip()]
            self.assertGreater(len(lines), 0)

    def test_router_block(self):
        """BLOCK verdict must write to activity feed and not dispatch."""
        from core.orchestrator.feedback_router import route
        import importlib
        import core.decision.decision_store as ds_mod

        with _TempRuntime() as rt:
            importlib.reload(ds_mod)
            d = self._make_decision(action="delete")
            result = route("BLOCK", d)
            self.assertEqual(result["routed_to"], "activity_feed")
            self.assertTrue(result.get("blocked"))

    def test_router_dispatch_no_op(self):
        """ALLOW + NO_ACTION must not dispatch any task."""
        from core.orchestrator.feedback_router import route
        import importlib
        import core.decision.decision_store as ds_mod

        with _TempRuntime():
            importlib.reload(ds_mod)
            d = self._make_decision(action="NO_ACTION")
            result = route("ALLOW", d)
            self.assertEqual(result["routed_to"], "dispatcher")
            self.assertFalse(result.get("dispatched"), "NO_ACTION should not dispatch")


# =========================================================================
# § 4 — End-to-End: run → interpretation → decision → policy → router
# =========================================================================

class TestAG18EndToEnd(unittest.TestCase):

    def test_e2e_nominal_flow(self):
        """Nominal state: classify → persist → gate ALLOW → router no-op."""
        from core.orchestrator.feedback_loop import run_loop
        import importlib
        import core.decision.decision_store as ds_mod

        with _TempRuntime() as rt:
            importlib.reload(ds_mod)
            result = run_loop(
                run_id="e2e-test-nominal",
                operator_status={"ok": True},
                runtime_status={"ok": True},
                policy_drift={"drift_count": 0},
            )
            self.assertIn(result["verdict"], ("ALLOW",))
            self.assertEqual(result["classification"], "nominal")
            # decision must be persisted
            latest = ds_mod.get_latest()
            self.assertIsNotNone(latest)
            self.assertEqual(latest["source_run_id"], "e2e-test-nominal")

    def test_e2e_drift_escalate(self):
        """Drift state with low-confidence action routes to operator queue."""
        from core.orchestrator.feedback_loop import run_loop
        import importlib
        import core.decision.decision_store as ds_mod

        with _TempRuntime() as rt:
            importlib.reload(ds_mod)
            result = run_loop(
                run_id="e2e-test-drift",
                operator_status={"ok": False},
                runtime_status={"ok": True},
                policy_drift={"drift_count": 3},
            )
            self.assertEqual(result["verdict"], "ESCALATE")
            # operator inbox must have an entry
            inbox = rt / "state" / "operator_inbox.jsonl"
            self.assertTrue(inbox.exists())


# =========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
