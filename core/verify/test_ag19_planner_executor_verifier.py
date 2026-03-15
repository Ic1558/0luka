"""AG-19: Tests for planner, executor, verifier, policy gate (plan-level).

Test suites:
  TestPlanCreation        (4) — create_plan pure function
  TestPlanPolicyGate      (3) — step_allowed + plan_allowed
  TestExecutorDispatch    (4) — execute_plan step routing
  TestVerifierOutcomes    (3) — verify_execution status derivation
  TestPolicyRetryLimit    (2) — retry budget enforcement
  TestOperatorEscalation  (2) — escalation path when plan blocked
  TestFeedbackLoopAG19    (2) — end-to-end run_loop AG-19 path
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure repo root on path
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


@contextmanager
def _TempRuntime():
    """Set LUKA_RUNTIME_ROOT to a fresh temp dir; clean up after."""
    with tempfile.TemporaryDirectory() as tmp:
        runtime = Path(tmp) / "runtime"
        runtime.mkdir()
        (runtime / "state").mkdir()
        (runtime / "logs").mkdir()
        (runtime / "artifacts").mkdir()
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
# TestPlanCreation
# ---------------------------------------------------------------------------

class TestPlanCreation(unittest.TestCase):

    def test_no_action_gives_empty_steps(self):
        from core.decision.models import DecisionRecord
        from core.planner.planner import create_plan
        record = DecisionRecord.make(
            source_run_id="run-001",
            classification="nominal",
            action="no_action",
            confidence=0.9,
        )
        plan = create_plan(record, run_state={"run_id": "run-001"})
        self.assertEqual(plan["steps"], [])
        self.assertEqual(plan["status"], "NO_OP")

    def test_retry_action_maps_to_retry_task_step(self):
        from core.decision.models import DecisionRecord
        from core.planner.planner import create_plan
        record = DecisionRecord.make(
            source_run_id="run-002",
            classification="degraded",
            action="retry",
            confidence=0.7,
        )
        plan = create_plan(record, run_state={"run_id": "run-002"})
        actions = [s["action"] for s in plan["steps"]]
        self.assertIn("retry_task", actions)
        self.assertEqual(plan["status"], "CREATED")

    def test_plan_id_is_deterministic_for_same_inputs(self):
        from core.decision.models import DecisionRecord
        from core.planner.planner import create_plan
        record = DecisionRecord.make(
            source_run_id="run-003",
            classification="nominal",
            action="no_action",
            confidence=0.9,
        )
        ts = "2026-01-01T00:00:00Z"
        plan1 = create_plan(record, run_state={"run_id": "run-003", "ts": ts})
        plan2 = create_plan(record, run_state={"run_id": "run-003", "ts": ts})
        self.assertEqual(plan1["plan_id"], plan2["plan_id"])

    def test_plan_contains_required_fields(self):
        from core.decision.models import DecisionRecord
        from core.planner.planner import create_plan
        record = DecisionRecord.make(
            source_run_id="run-004",
            classification="degraded",
            action="retry",
            confidence=0.8,
        )
        plan = create_plan(record, run_state={"run_id": "run-004"})
        for field in ("plan_id", "run_id", "decision_id", "created_at", "steps", "status"):
            self.assertIn(field, plan, f"missing field: {field}")


# ---------------------------------------------------------------------------
# TestPlanPolicyGate
# ---------------------------------------------------------------------------

class TestPlanPolicyGate(unittest.TestCase):

    def test_step_allowed_verify_artifacts(self):
        from core.policy.policy_gate import step_allowed
        self.assertEqual(step_allowed({"action": "verify_artifacts"}), "ALLOW")

    def test_step_allowed_retry_task(self):
        from core.policy.policy_gate import step_allowed
        self.assertEqual(step_allowed({"action": "retry_task"}), "ALLOW")

    def test_plan_allowed_empty_steps(self):
        from core.policy.policy_gate import plan_allowed
        self.assertEqual(plan_allowed({"steps": []}), "ALLOW")

    def test_plan_blocked_on_destructive_step(self):
        from core.policy.policy_gate import plan_allowed
        plan = {"steps": [{"action": "delete"}]}
        self.assertEqual(plan_allowed(plan), "BLOCK")

    def test_plan_escalated_on_unknown_step(self):
        from core.policy.policy_gate import plan_allowed
        plan = {"steps": [{"action": "unknown_action"}]}
        self.assertEqual(plan_allowed(plan), "ESCALATE")


# ---------------------------------------------------------------------------
# TestExecutorDispatch
# ---------------------------------------------------------------------------

class TestExecutorDispatch(unittest.TestCase):

    def test_empty_plan_is_no_op(self):
        from core.executor.executor import execute_plan
        result = execute_plan({"plan_id": "p1", "run_id": "r1", "steps": []})
        self.assertEqual(result["status"], "NO_OP")
        self.assertEqual(result["executed_steps"], [])

    def test_verify_artifacts_step_executes(self):
        from core.executor.executor import execute_plan
        with _TempRuntime():
            result = execute_plan({
                "plan_id": "p2",
                "run_id": "r2",
                "steps": [{"action": "verify_artifacts"}],
            })
        self.assertIn("executed_steps", result)
        steps = result["executed_steps"]
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["step"], "verify_artifacts")

    def test_disallowed_step_sets_ok_false(self):
        from core.executor.executor import execute_plan
        result = execute_plan({
            "plan_id": "p3",
            "run_id": "r3",
            "steps": [{"action": "rm_rf"}],
        })
        self.assertFalse(result["executed_steps"][0]["ok"])
        self.assertEqual(result["executed_steps"][0]["reason"], "disallowed_action")

    def test_execution_result_has_required_fields(self):
        from core.executor.executor import execute_plan
        result = execute_plan({"plan_id": "p4", "run_id": "r4", "steps": []})
        for f in ("execution_id", "plan_id", "run_id", "started_at", "completed_at", "status"):
            self.assertIn(f, result, f"missing: {f}")


# ---------------------------------------------------------------------------
# TestVerifierOutcomes
# ---------------------------------------------------------------------------

class TestVerifierOutcomes(unittest.TestCase):

    def test_success_when_all_steps_ok(self):
        from core.verifier.verifier import verify_execution
        with _TempRuntime():
            result = verify_execution("run-v1", {
                "execution_id": "exec1",
                "status": "SUCCESS",
                "executed_steps": [{"ok": True}],
            })
        self.assertEqual(result["status"], "SUCCESS")

    def test_failed_when_status_failed(self):
        from core.verifier.verifier import verify_execution
        with _TempRuntime():
            result = verify_execution("run-v2", {
                "execution_id": "exec2",
                "status": "FAILED",
                "executed_steps": [],
            })
        self.assertEqual(result["status"], "FAILED")

    def test_partial_when_some_steps_ok(self):
        from core.verifier.verifier import verify_execution
        with _TempRuntime():
            result = verify_execution("run-v3", {
                "execution_id": "exec3",
                "status": "",
                "executed_steps": [{"ok": True}, {"ok": False}],
            })
        self.assertEqual(result["status"], "PARTIAL")

    def test_verification_result_has_required_fields(self):
        from core.verifier.verifier import verify_execution
        with _TempRuntime():
            result = verify_execution("run-v4", {
                "execution_id": "exec4",
                "status": "NO_OP",
                "executed_steps": [],
            })
        for f in ("verification_id", "run_id", "execution_id", "status", "verified_at", "reason"):
            self.assertIn(f, result, f"missing: {f}")


# ---------------------------------------------------------------------------
# TestPolicyRetryLimit
# ---------------------------------------------------------------------------

class TestPolicyRetryLimit(unittest.TestCase):

    def test_retry_allowed_when_no_prior_retries(self):
        from core.policy.policy_gate import plan_allowed
        plan = {
            "run_id": "run-r1",
            "steps": [{"action": "retry_task"}],
        }
        self.assertEqual(plan_allowed(plan, prior_plans=[]), "ALLOW")

    def test_retry_blocked_when_prior_retry_exists(self):
        from core.policy.policy_gate import plan_allowed
        prior = [{
            "run_id": "run-r2",
            "steps": [{"action": "retry_task"}],
        }]
        plan = {
            "run_id": "run-r2",
            "steps": [{"action": "retry_task"}],
        }
        self.assertEqual(plan_allowed(plan, prior_plans=prior), "BLOCK")


# ---------------------------------------------------------------------------
# TestOperatorEscalation
# ---------------------------------------------------------------------------

class TestOperatorEscalation(unittest.TestCase):

    def test_verdict_block_routes_to_operator_queue(self):
        """When policy_verdict returns BLOCK, run_loop should route to operator queue."""
        from core.orchestrator import feedback_loop
        with _TempRuntime() as rt:
            with patch("core.orchestrator.feedback_loop.policy_verdict", return_value="BLOCK"), \
                 patch("core.orchestrator.feedback_loop.enqueue_operator_case") as mock_enq:
                result = feedback_loop.run_loop(
                    run_id="block-run",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            mock_enq.assert_called_once()
            self.assertEqual(result["verdict"], "BLOCK")
            self.assertEqual(result["result"]["routed"], "operator_queue")

    def test_plan_verdict_block_routes_to_operator_queue(self):
        """When plan_allowed returns BLOCK, run_loop escalates."""
        from core.orchestrator import feedback_loop
        with _TempRuntime() as rt:
            with patch("core.orchestrator.feedback_loop.policy_verdict", return_value="ALLOW"), \
                 patch("core.orchestrator.feedback_loop.plan_allowed", return_value="BLOCK"), \
                 patch("core.orchestrator.feedback_loop.enqueue_operator_case") as mock_enq:
                result = feedback_loop.run_loop(
                    run_id="plan-block-run",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            mock_enq.assert_called_once()
            self.assertIn("plan_verdict", result)
            self.assertEqual(result["plan_verdict"], "BLOCK")


# ---------------------------------------------------------------------------
# TestFeedbackLoopAG19 (end-to-end)
# ---------------------------------------------------------------------------

class TestFeedbackLoopAG19(unittest.TestCase):

    def test_full_loop_no_op_plan(self):
        """no_action classification → NO_OP plan → SUCCESS verification → no escalation."""
        from core.orchestrator import feedback_loop
        with _TempRuntime():
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"):
                result = feedback_loop.run_loop(
                    run_id="e2e-noop",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
        self.assertIn("verdict", result)
        self.assertEqual(result["verdict"], "ALLOW")
        self.assertIn("execution_status", result)

    def test_full_loop_produces_all_ids(self):
        """ALLOW path should produce decision_id, plan_id, execution_id, verification_id."""
        from core.orchestrator import feedback_loop
        with _TempRuntime():
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"):
                result = feedback_loop.run_loop(
                    run_id="e2e-ids",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
        for field in ("decision_id", "plan_id", "execution_id", "verification_id"):
            self.assertIn(field, result, f"missing: {field}")


if __name__ == "__main__":
    unittest.main()
