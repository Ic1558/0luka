"""AG-24: Tests for safety modules — emergency_stop, protected_zone_guard,
autonomy_budget, runtime_safety_gate, topology_transition_gate.

Suites:
  TestEmergencyStop          (6)
  TestProtectedZoneGuard     (6)
  TestAutonomyBudget         (5)
  TestRuntimeSafetyGate      (6)
  TestTopologyTransitionGate (4)
  TestSovereignLoopInteg     (2)
  TestFeedbackLoopInteg      (2)
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
# TestEmergencyStop
# ---------------------------------------------------------------------------

class TestEmergencyStop(unittest.TestCase):

    def test_inactive_by_default(self):
        from core.safety.emergency_stop import is_emergency_stop_active
        with _TempRuntime():
            self.assertFalse(is_emergency_stop_active())

    def test_activate_sets_active(self):
        from core.safety.emergency_stop import activate_emergency_stop, is_emergency_stop_active
        with _TempRuntime():
            activate_emergency_stop("test_reason")
            self.assertTrue(is_emergency_stop_active())

    def test_clear_deactivates(self):
        from core.safety.emergency_stop import activate_emergency_stop, clear_emergency_stop, is_emergency_stop_active
        with _TempRuntime():
            activate_emergency_stop("test")
            clear_emergency_stop("operator_1")
            self.assertFalse(is_emergency_stop_active())

    def test_state_persists_to_file(self):
        from core.safety.emergency_stop import activate_emergency_stop, get_emergency_stop_state
        with _TempRuntime() as rt:
            activate_emergency_stop("persist_test")
            state_file = rt / "state" / "emergency_stop.json"
            self.assertTrue(state_file.exists())
            state = json.loads(state_file.read_text())
            self.assertTrue(state["active"])
            self.assertEqual(state["reason"], "persist_test")

    def test_activate_idempotent(self):
        from core.safety.emergency_stop import activate_emergency_stop, get_emergency_stop_state
        with _TempRuntime():
            activate_emergency_stop("first")
            activate_emergency_stop("second")  # should not overwrite
            state = get_emergency_stop_state()
            self.assertEqual(state["reason"], "first")

    def test_no_runtime_root_returns_false(self):
        from core.safety import emergency_stop as es_mod
        old = os.environ.pop("LUKA_RUNTIME_ROOT", None)
        try:
            self.assertFalse(es_mod.is_emergency_stop_active())
        finally:
            if old:
                os.environ["LUKA_RUNTIME_ROOT"] = old


# ---------------------------------------------------------------------------
# TestProtectedZoneGuard
# ---------------------------------------------------------------------------

class TestProtectedZoneGuard(unittest.TestCase):

    def test_git_write_blocked(self):
        from core.safety.protected_zone_guard import assert_path_safe
        with _TempRuntime():
            result = assert_path_safe("/Users/icmini/0luka/.git/objects/pack/pack.idx", "write")
            self.assertEqual(result, "BLOCK")

    def test_git_delete_blocked(self):
        from core.safety.protected_zone_guard import assert_path_safe
        with _TempRuntime():
            result = assert_path_safe("/repo/.git/index", "delete")
            self.assertEqual(result, "BLOCK")

    def test_launchd_plist_write_blocked(self):
        from core.safety.protected_zone_guard import assert_path_safe
        with _TempRuntime():
            result = assert_path_safe("/Users/icmini/Library/LaunchAgents/com.0luka.foo.plist", "write")
            self.assertEqual(result, "BLOCK")

    def test_normal_path_allowed(self):
        from core.safety.protected_zone_guard import assert_path_safe
        with _TempRuntime():
            result = assert_path_safe("/Users/icmini/0luka/core/health.py", "read")
            self.assertEqual(result, "ALLOW")

    def test_git_read_escalates(self):
        from core.safety.protected_zone_guard import assert_path_safe
        with _TempRuntime():
            result = assert_path_safe("/repo/.git/config", "read")
            self.assertEqual(result, "ESCALATE")

    def test_violation_logged(self):
        from core.safety.protected_zone_guard import assert_path_safe, get_recent_violations
        with _TempRuntime():
            assert_path_safe("/repo/.git/index", "write")
            violations = get_recent_violations()
            self.assertGreater(len(violations), 0)
            self.assertEqual(violations[-1]["verdict"], "BLOCK")


# ---------------------------------------------------------------------------
# TestAutonomyBudget
# ---------------------------------------------------------------------------

class TestAutonomyBudget(unittest.TestCase):

    def test_fresh_budget_not_exhausted(self):
        from core.safety.autonomy_budget import budget_exhausted
        with _TempRuntime():
            self.assertFalse(budget_exhausted("run-fresh"))

    def test_consume_within_budget_returns_true(self):
        from core.safety.autonomy_budget import consume_budget
        with _TempRuntime():
            result = consume_budget("run-c1", "retry")
            self.assertTrue(result)

    def test_budget_exhausted_after_ceiling(self):
        from core.safety.autonomy_budget import consume_budget, budget_exhausted
        with _TempRuntime():
            consume_budget("run-x1", "retry")  # ceiling=1 → exhausted
            consume_budget("run-x1", "retry")  # over ceiling
            self.assertTrue(budget_exhausted("run-x1"))

    def test_consume_over_ceiling_returns_false(self):
        from core.safety.autonomy_budget import consume_budget
        with _TempRuntime():
            consume_budget("run-x2", "retry")
            result = consume_budget("run-x2", "retry")  # second exceeds ceiling=1
            self.assertFalse(result)

    def test_budget_state_has_remaining(self):
        from core.safety.autonomy_budget import get_budget_state
        with _TempRuntime():
            state = get_budget_state("run-s1")
            self.assertIn("remaining", state)
            self.assertIn("retry", state["remaining"])


# ---------------------------------------------------------------------------
# TestRuntimeSafetyGate
# ---------------------------------------------------------------------------

class TestRuntimeSafetyGate(unittest.TestCase):

    def test_allow_on_clean_context(self):
        from core.safety.runtime_safety_gate import evaluate_runtime_safety
        with _TempRuntime():
            result = evaluate_runtime_safety({
                "run_id": "rsg-1", "action_type": "inspect",
                "policy_verdict": "ALLOW", "topology_mode": "STABLE",
                "process_conflict": False, "failure_count": 0,
                "emergency_stop": False, "protected_zone": False,
            })
            self.assertEqual(result, "ALLOW")

    def test_stop_when_emergency_stop_active(self):
        from core.safety.runtime_safety_gate import evaluate_runtime_safety
        with _TempRuntime():
            result = evaluate_runtime_safety({
                "run_id": "rsg-2", "action_type": "retry",
                "emergency_stop": True,
            })
            self.assertEqual(result, "STOP")

    def test_block_when_policy_block(self):
        from core.safety.runtime_safety_gate import evaluate_runtime_safety
        with _TempRuntime():
            result = evaluate_runtime_safety({
                "run_id": "rsg-3", "action_type": "retry",
                "policy_verdict": "BLOCK", "emergency_stop": False,
            })
            self.assertEqual(result, "BLOCK")

    def test_block_on_protected_zone(self):
        from core.safety.runtime_safety_gate import evaluate_runtime_safety
        with _TempRuntime():
            result = evaluate_runtime_safety({
                "run_id": "rsg-4", "action_type": "write",
                "policy_verdict": "ALLOW", "emergency_stop": False,
                "protected_zone": True,
            })
            self.assertEqual(result, "BLOCK")

    def test_escalate_on_process_conflict(self):
        from core.safety.runtime_safety_gate import evaluate_runtime_safety
        with _TempRuntime():
            result = evaluate_runtime_safety({
                "run_id": "rsg-5", "action_type": "retry",
                "policy_verdict": "ALLOW", "emergency_stop": False,
                "process_conflict": True,
            })
            self.assertEqual(result, "ESCALATE")

    def test_block_on_budget_exhausted(self):
        from core.safety.runtime_safety_gate import evaluate_runtime_safety
        from core.safety.autonomy_budget import consume_budget
        with _TempRuntime():
            consume_budget("rsg-6", "retry")  # exhaust retry budget
            result = evaluate_runtime_safety({
                "run_id": "rsg-6", "action_type": "retry",
                "policy_verdict": "ALLOW", "emergency_stop": False,
                "process_conflict": False, "failure_count": 0,
                "protected_zone": False, "topology_mode": "STABLE",
            })
            self.assertEqual(result, "BLOCK")


# ---------------------------------------------------------------------------
# TestTopologyTransitionGate
# ---------------------------------------------------------------------------

class TestTopologyTransitionGate(unittest.TestCase):

    def test_allow_non_sensitive_action(self):
        from core.safety.topology_transition_gate import evaluate_transition
        with _TempRuntime():
            result = evaluate_transition({"action": "inspect_artifacts"})
            self.assertEqual(result, "ALLOW")

    def test_allow_sensitive_action_when_stable(self):
        from core.safety.topology_transition_gate import evaluate_transition, set_topology_mode
        with _TempRuntime():
            set_topology_mode("STABLE")
            result = evaluate_transition({"action": "policy_rollout"})
            self.assertEqual(result, "ALLOW")

    def test_drain_required_when_draining(self):
        from core.safety.topology_transition_gate import evaluate_transition, set_topology_mode
        with _TempRuntime():
            set_topology_mode("DRAINING")
            result = evaluate_transition({"action": "policy_rollout"})
            self.assertEqual(result, "DRAIN_REQUIRED")

    def test_block_on_lockdown(self):
        from core.safety.topology_transition_gate import evaluate_transition, set_topology_mode
        with _TempRuntime():
            set_topology_mode("LOCKDOWN")
            result = evaluate_transition({"action": "policy_rollout"})
            self.assertEqual(result, "BLOCK")


# ---------------------------------------------------------------------------
# TestSovereignLoopInteg — emergency_stop blocks sovereign action path
# ---------------------------------------------------------------------------

class TestSovereignLoopInteg(unittest.TestCase):

    def test_emergency_stop_blocks_feedback_loop_call(self):
        from tools.ops.sovereign_loop import SovereignControl
        with _TempRuntime():
            from core.safety.emergency_stop import activate_emergency_stop
            activate_emergency_stop("integration_test")
            ctrl = SovereignControl(confirmed=False, replay_mode=True)
            ctrl.index_status = "healthy"
            ctrl.triggers_found = []
            # _safety_check_blocks() should return True
            self.assertTrue(ctrl._safety_check_blocks())

    def test_no_stop_when_inactive(self):
        from tools.ops.sovereign_loop import SovereignControl
        with _TempRuntime():
            ctrl = SovereignControl(confirmed=False, replay_mode=True)
            ctrl.index_status = "healthy"
            ctrl.triggers_found = []
            self.assertFalse(ctrl._safety_check_blocks())


# ---------------------------------------------------------------------------
# TestFeedbackLoopInteg — emergency_stop halts feedback_loop action path
# ---------------------------------------------------------------------------

class TestFeedbackLoopInteg(unittest.TestCase):

    def test_feedback_loop_halted_by_emergency_stop(self):
        from core.orchestrator import feedback_loop
        with _TempRuntime():
            from core.safety.emergency_stop import activate_emergency_stop
            activate_emergency_stop("loop_test")
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"):
                result = feedback_loop.run_loop(
                    run_id="es-loop-test",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            self.assertEqual(result["result"]["routed"], "emergency_stop")

    def test_feedback_loop_proceeds_when_stop_inactive(self):
        from core.orchestrator import feedback_loop
        with _TempRuntime():
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"):
                result = feedback_loop.run_loop(
                    run_id="no-stop-test",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            self.assertIn("verdict", result)
            self.assertNotEqual(result.get("result", {}).get("routed"), "emergency_stop")


if __name__ == "__main__":
    unittest.main()
