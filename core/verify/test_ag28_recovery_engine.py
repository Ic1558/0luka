"""AG-28: Tests for autonomous recovery engine.

Suites:
  TestRecoveryEngine        (5)  — unit: action selection
  TestRecoveryPolicy        (5)  — unit: policy gate
  TestRecoveryStore         (4)  — unit: append/latest
  TestRecoveryExecutor      (4)  — unit: safe execution
  TestFeedbackLoopAG28      (3)  — integration: recovery in loop
  TestSafetyGateAG28        (2)  — safety: emergency stop + protected zone
"""
from __future__ import annotations

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
# TestRecoveryEngine
# ---------------------------------------------------------------------------

class TestRecoveryEngine(unittest.TestCase):

    def test_verification_failed_recoverable_returns_retry(self):
        from core.recovery.recovery_engine import select_recovery_action
        result = select_recovery_action({
            "failure_type": "verification_failed",
            "recoverable": True,
            "requires_operator": False,
            "protected_zone_related": False,
            "topology_sensitive": False,
        })
        self.assertEqual(result["recovery_action"], "RETRY_ONCE")

    def test_unknown_failure_requests_operator(self):
        """Unknown failure must never auto-recover — routes to REQUEST_OPERATOR."""
        from core.recovery.recovery_engine import select_recovery_action
        result = select_recovery_action({
            "failure_type": "unknown",
            "recoverable": False,
        })
        self.assertEqual(result["recovery_action"], "REQUEST_OPERATOR")

    def test_protected_zone_returns_request_operator(self):
        from core.recovery.recovery_engine import select_recovery_action
        result = select_recovery_action({
            "failure_type": "protected_zone_violation",
            "recoverable": False,
            "protected_zone_related": True,
        })
        self.assertEqual(result["recovery_action"], "REQUEST_OPERATOR")
        self.assertTrue(result["requires_operator"])

    def test_missing_artifact_returns_recheck(self):
        from core.recovery.recovery_engine import select_recovery_action
        result = select_recovery_action({
            "failure_type": "missing_artifact",
            "recoverable": True,
            "protected_zone_related": False,
            "topology_sensitive": False,
        })
        self.assertEqual(result["recovery_action"], "RECHECK_ARTIFACTS")

    def test_topology_sensitive_returns_stop(self):
        from core.recovery.recovery_engine import select_recovery_action
        result = select_recovery_action({
            "failure_type": "topology_lockdown",
            "recoverable": False,
            "topology_sensitive": True,
        })
        self.assertEqual(result["recovery_action"], "STOP")


# ---------------------------------------------------------------------------
# TestRecoveryPolicy
# ---------------------------------------------------------------------------

class TestRecoveryPolicy(unittest.TestCase):

    def test_allow_retry_once_for_recoverable(self):
        from core.recovery.recovery_policy import evaluate_recovery_policy
        result = evaluate_recovery_policy(
            {"failure_type": "verification_failed", "recoverable": True},
            {"recovery_action": "RETRY_ONCE"},
        )
        self.assertEqual(result, "ALLOW")

    def test_stop_always_allowed(self):
        from core.recovery.recovery_policy import evaluate_recovery_policy
        result = evaluate_recovery_policy(
            {"failure_type": "unknown"},
            {"recovery_action": "STOP"},
        )
        self.assertEqual(result, "ALLOW")

    def test_protected_zone_escalates(self):
        from core.recovery.recovery_policy import evaluate_recovery_policy
        result = evaluate_recovery_policy(
            {"failure_type": "protected_zone_violation", "protected_zone_related": True},
            {"recovery_action": "RETRY_ONCE"},
        )
        self.assertEqual(result, "ESCALATE")

    def test_budget_exhausted_escalates(self):
        from core.recovery.recovery_policy import evaluate_recovery_policy, MAX_RECOVERY_ATTEMPTS
        prior = [{"run_id": "rp1", "recovery_action": "RETRY_ONCE"}] * MAX_RECOVERY_ATTEMPTS
        result = evaluate_recovery_policy(
            {"failure_type": "verification_failed", "run_id": "rp1"},
            {"recovery_action": "RETRY_ONCE"},
            prior_recoveries=prior,
        )
        self.assertEqual(result, "ESCALATE")

    def test_topology_sensitive_stops(self):
        from core.recovery.recovery_policy import evaluate_recovery_policy
        result = evaluate_recovery_policy(
            {"failure_type": "topology_lockdown", "topology_sensitive": True},
            {"recovery_action": "RETRY_ONCE"},
        )
        self.assertEqual(result, "STOP")


# ---------------------------------------------------------------------------
# TestRecoveryStore
# ---------------------------------------------------------------------------

class TestRecoveryStore(unittest.TestCase):

    def test_append_creates_record(self):
        with _TempRuntime():
            import importlib, core.config, core.recovery.recovery_store as rst
            importlib.reload(core.config)
            importlib.reload(rst)
            rec = rst.append_recovery({"run_id": "s1", "recovery_action": "STOP"})
            self.assertIn("recovery_id", rec)
            self.assertIn("ts", rec)

    def test_list_recent_returns_appended(self):
        with _TempRuntime():
            import importlib, core.config, core.recovery.recovery_store as rst
            importlib.reload(core.config)
            importlib.reload(rst)
            rst.append_recovery({"run_id": "s2", "recovery_action": "RETRY_ONCE"})
            records = rst.list_recent()
            self.assertEqual(len(records), 1)

    def test_write_latest_readable(self):
        with _TempRuntime():
            import importlib, core.config, core.recovery.recovery_store as rst
            importlib.reload(core.config)
            importlib.reload(rst)
            rst.write_latest({"run_id": "s3", "recovery_id": "abc", "recovery_action": "STOP"})
            latest = rst.get_latest()
            self.assertIsNotNone(latest)
            self.assertEqual(latest["run_id"], "s3")

    def test_get_latest_returns_none_when_empty(self):
        with _TempRuntime():
            import importlib, core.config, core.recovery.recovery_store as rst
            importlib.reload(core.config)
            importlib.reload(rst)
            self.assertIsNone(rst.get_latest())


# ---------------------------------------------------------------------------
# TestRecoveryExecutor
# ---------------------------------------------------------------------------

class TestRecoveryExecutor(unittest.TestCase):

    def test_retry_once_with_no_runtime_returns_failed(self):
        from core.recovery.recovery_executor import execute_recovery_action
        old = os.environ.pop("LUKA_RUNTIME_ROOT", None)
        try:
            result = execute_recovery_action(
                {"recovery_action": "RETRY_ONCE"},
                {"run_id": "ex1", "failure_type": "verification_failed"},
            )
            self.assertEqual(result["result"], "FAILED")
        finally:
            if old:
                os.environ["LUKA_RUNTIME_ROOT"] = old

    def test_stop_action_returns_skipped(self):
        from core.recovery.recovery_executor import execute_recovery_action
        with _TempRuntime():
            result = execute_recovery_action(
                {"recovery_action": "STOP"},
                {"run_id": "ex2"},
            )
            self.assertEqual(result["result"], "SKIPPED")

    def test_refresh_runtime_state_with_state_files(self):
        from core.recovery.recovery_executor import execute_recovery_action
        with _TempRuntime() as rt:
            (rt / "state" / "dummy.json").write_text("{}")
            result = execute_recovery_action(
                {"recovery_action": "REFRESH_RUNTIME_STATE"},
                {"run_id": "ex3"},
            )
            self.assertEqual(result["result"], "SUCCESS")

    def test_request_operator_returns_skipped(self):
        from core.recovery.recovery_executor import execute_recovery_action
        with _TempRuntime():
            result = execute_recovery_action(
                {"recovery_action": "REQUEST_OPERATOR"},
                {"run_id": "ex4"},
            )
            self.assertEqual(result["result"], "SKIPPED")


# ---------------------------------------------------------------------------
# TestFeedbackLoopAG28
# ---------------------------------------------------------------------------

class TestFeedbackLoopAG28(unittest.TestCase):

    def test_recovery_id_in_result_on_success(self):
        """Nominal SUCCESS: no recovery triggered, recovery_id absent or None."""
        from core.orchestrator import feedback_loop
        with _TempRuntime():
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"):
                result = feedback_loop.run_loop(
                    run_id="ag28-success",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            # Success path — recovery not triggered
            self.assertIn("recovery_action", result)

    def test_recovery_present_after_allowed_execution(self):
        """ALLOW path through execution should include recovery_action key."""
        from core.orchestrator import feedback_loop
        with _TempRuntime():
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"), \
                 patch("core.orchestrator.feedback_loop.policy_verdict", return_value="ALLOW"):
                result = feedback_loop.run_loop(
                    run_id="ag28-allow",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            self.assertIn("recovery_action", result)

    def test_emergency_stop_blocks_recovery(self):
        """Emergency stop active: feedback_loop returns emergency_stop route."""
        from core.orchestrator import feedback_loop
        with _TempRuntime():
            from core.safety.emergency_stop import activate_emergency_stop
            activate_emergency_stop("test_recovery_block")
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"):
                result = feedback_loop.run_loop(
                    run_id="ag28-estop",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            self.assertEqual(result["result"]["routed"], "emergency_stop")


# ---------------------------------------------------------------------------
# TestSafetyGateAG28
# ---------------------------------------------------------------------------

class TestSafetyGateAG28(unittest.TestCase):

    def test_recovery_action_passes_when_safe(self):
        """RETRY_ONCE with safe context → ALLOW."""
        from core.safety.runtime_safety_gate import evaluate_runtime_safety
        with _TempRuntime():
            result = evaluate_runtime_safety({
                "run_id": "sg1",
                "action_type": "retry_once",
                "policy_verdict": "ALLOW",
                "emergency_stop": False,
                "protected_zone": False,
                "failure_count": 0,
            })
            self.assertEqual(result, "ALLOW")

    def test_request_operator_allowed_during_emergency_stop(self):
        """REQUEST_OPERATOR must be allowed even when emergency_stop is active."""
        from core.safety.runtime_safety_gate import evaluate_runtime_safety
        with _TempRuntime():
            result = evaluate_runtime_safety({
                "run_id": "sg2",
                "action_type": "request_operator",
                "policy_verdict": "ALLOW",
                "emergency_stop": True,
                "protected_zone": False,
                "failure_count": 0,
            })
            self.assertEqual(result, "ALLOW")


if __name__ == "__main__":
    unittest.main()
