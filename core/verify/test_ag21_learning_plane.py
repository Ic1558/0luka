"""AG-21: Tests for learning plane.

Suites:
  TestObservationStore      (4)  — unit
  TestPatternExtractor      (4)  — unit
  TestPolicyCandidates      (4)  — unit
  TestLearningMetrics       (2)  — unit
  TestPolicyGateSignals     (2)  — policy_gate learning metadata
  TestFeedbackLoopAG21      (3)  — integration: loop emits observations
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
# TestObservationStore
# ---------------------------------------------------------------------------

class TestObservationStore(unittest.TestCase):

    def test_append_creates_entry(self):
        with _TempRuntime():
            import importlib, core.config, learning.observation_store as obs
            importlib.reload(core.config)
            importlib.reload(obs)
            rec = obs.append_observation({"run_id": "r1", "execution_result": "SUCCESS"})
            self.assertIn("observation_id", rec)
            self.assertIn("timestamp", rec)

    def test_get_recent_returns_appended(self):
        with _TempRuntime():
            import importlib, core.config, learning.observation_store as obs
            importlib.reload(core.config)
            importlib.reload(obs)
            obs.append_observation({"run_id": "r2", "execution_result": "FAILED"})
            records = obs.get_recent_observations(limit=10)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["run_id"], "r2")

    def test_get_by_run_id_filters(self):
        with _TempRuntime():
            import importlib, core.config, learning.observation_store as obs
            importlib.reload(core.config)
            importlib.reload(obs)
            obs.append_observation({"run_id": "r3a", "execution_result": "SUCCESS"})
            obs.append_observation({"run_id": "r3b", "execution_result": "FAILED"})
            result = obs.get_observations_by_run("r3a")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["run_id"], "r3a")

    def test_empty_store_returns_empty_list(self):
        with _TempRuntime():
            import importlib, core.config, learning.observation_store as obs
            importlib.reload(core.config)
            importlib.reload(obs)
            self.assertEqual(obs.get_recent_observations(), [])


# ---------------------------------------------------------------------------
# TestPatternExtractor
# ---------------------------------------------------------------------------

class TestPatternExtractor(unittest.TestCase):

    def test_no_pattern_below_min_observations(self):
        with _TempRuntime():
            import importlib, core.config, learning.observation_store as obs
            import learning.pattern_extractor as pe
            importlib.reload(core.config)
            importlib.reload(obs)
            importlib.reload(pe)
            # Only 2 failures — below MIN_OBSERVATIONS=3
            for _ in range(2):
                obs.append_observation({"run_id": "p1", "execution_result": "FAILED"})
            patterns = pe.extract_patterns()
            exec_fail_patterns = [p for p in patterns if p.pattern_type == "repeated_executor_failure"]
            self.assertEqual(len(exec_fail_patterns), 0)

    def test_pattern_detected_at_min_observations(self):
        with _TempRuntime():
            import importlib, core.config, learning.observation_store as obs
            import learning.pattern_extractor as pe
            importlib.reload(core.config)
            importlib.reload(obs)
            importlib.reload(pe)
            for _ in range(3):
                obs.append_observation({"run_id": "p2", "execution_result": "FAILED"})
            patterns = pe.extract_patterns()
            types = [p.pattern_type for p in patterns]
            self.assertIn("repeated_executor_failure", types)

    def test_update_registry_persists(self):
        with _TempRuntime() as rt:
            import importlib, core.config, learning.observation_store as obs
            import learning.pattern_extractor as pe
            importlib.reload(core.config)
            importlib.reload(obs)
            importlib.reload(pe)
            for _ in range(3):
                obs.append_observation({"run_id": "p3", "execution_result": "FAILED"})
            pe.update_pattern_registry()
            registry_path = rt / "state" / "pattern_registry.json"
            self.assertTrue(registry_path.exists())
            data = json.loads(registry_path.read_text())
            self.assertIsInstance(data, list)

    def test_get_patterns_returns_registry(self):
        with _TempRuntime() as rt:
            import importlib, core.config, learning.observation_store as obs
            import learning.pattern_extractor as pe
            importlib.reload(core.config)
            importlib.reload(obs)
            importlib.reload(pe)
            for _ in range(3):
                obs.append_observation({"run_id": "p4", "execution_result": "FAILED"})
            pe.update_pattern_registry()
            patterns = pe.get_patterns()
            self.assertGreater(len(patterns), 0)


# ---------------------------------------------------------------------------
# TestPolicyCandidates
# ---------------------------------------------------------------------------

class TestPolicyCandidates(unittest.TestCase):

    def test_no_candidates_without_patterns(self):
        with _TempRuntime():
            import importlib, core.config, learning.observation_store as obs
            import learning.pattern_extractor as pe
            import learning.policy_candidates as pc
            importlib.reload(core.config)
            importlib.reload(obs)
            importlib.reload(pe)
            importlib.reload(pc)
            candidates = pc.generate_policy_candidates()
            self.assertEqual(candidates, [])

    def test_candidates_generated_from_pattern(self):
        with _TempRuntime():
            import importlib, core.config, learning.observation_store as obs
            import learning.pattern_extractor as pe
            import learning.policy_candidates as pc
            importlib.reload(core.config)
            importlib.reload(obs)
            importlib.reload(pe)
            importlib.reload(pc)
            for _ in range(3):
                obs.append_observation({"run_id": "c1", "execution_result": "FAILED"})
            pe.update_pattern_registry()
            candidates = pc.generate_policy_candidates()
            self.assertGreater(len(candidates), 0)
            self.assertEqual(candidates[0]["approval_state"], "PENDING")

    def test_candidate_approval_state_is_pending(self):
        with _TempRuntime():
            import importlib, core.config, learning.observation_store as obs
            import learning.pattern_extractor as pe
            import learning.policy_candidates as pc
            importlib.reload(core.config)
            importlib.reload(obs)
            importlib.reload(pe)
            importlib.reload(pc)
            for _ in range(3):
                obs.append_observation({"run_id": "c2", "execution_result": "FAILED"})
            pe.update_pattern_registry()
            pc.generate_policy_candidates()
            candidates = pc.list_candidates()
            for c in candidates:
                self.assertEqual(c["approval_state"], "PENDING")

    def test_no_duplicate_candidates_for_same_pattern(self):
        with _TempRuntime():
            import importlib, core.config, learning.observation_store as obs
            import learning.pattern_extractor as pe
            import learning.policy_candidates as pc
            importlib.reload(core.config)
            importlib.reload(obs)
            importlib.reload(pe)
            importlib.reload(pc)
            for _ in range(3):
                obs.append_observation({"run_id": "c3", "execution_result": "FAILED"})
            pe.update_pattern_registry()
            pc.generate_policy_candidates()
            pc.generate_policy_candidates()  # second call — should not duplicate
            candidates = pc.list_candidates()
            pattern_ids = [c["pattern_id"] for c in candidates]
            self.assertEqual(len(pattern_ids), len(set(pattern_ids)))


# ---------------------------------------------------------------------------
# TestLearningMetrics
# ---------------------------------------------------------------------------

class TestLearningMetrics(unittest.TestCase):

    def test_metrics_has_required_keys(self):
        with _TempRuntime():
            import importlib, core.config, learning.learning_metrics as lm
            importlib.reload(core.config)
            importlib.reload(lm)
            metrics = lm.get_learning_metrics()
            for key in ("observation_count", "patterns_detected",
                        "policy_candidates_generated", "candidate_pending", "computed_at"):
                self.assertIn(key, metrics)

    def test_metrics_counts_observations(self):
        with _TempRuntime():
            import importlib, core.config
            import learning.observation_store as obs
            import learning.learning_metrics as lm
            importlib.reload(core.config)
            importlib.reload(obs)
            importlib.reload(lm)
            obs.append_observation({"run_id": "m1", "execution_result": "SUCCESS"})
            obs.append_observation({"run_id": "m2", "execution_result": "FAILED"})
            metrics = lm.get_learning_metrics()
            self.assertEqual(metrics["observation_count"], 2)


# ---------------------------------------------------------------------------
# TestPolicyGateSignals
# ---------------------------------------------------------------------------

class TestPolicyGateSignals(unittest.TestCase):

    def test_block_verdict_has_learning_signal(self):
        from core.policy.policy_gate import policy_verdict_with_learning_signal
        result = policy_verdict_with_learning_signal({"action": "delete", "confidence": 0.9})
        self.assertEqual(result["verdict"], "BLOCK")
        self.assertTrue(result["learning_signal"])
        self.assertIn("policy_block", result["pattern_tag"])

    def test_allow_verdict_has_no_learning_signal(self):
        from core.policy.policy_gate import policy_verdict_with_learning_signal
        result = policy_verdict_with_learning_signal({"action": "no_action", "confidence": 0.9})
        self.assertEqual(result["verdict"], "ALLOW")
        self.assertFalse(result["learning_signal"])


# ---------------------------------------------------------------------------
# TestFeedbackLoopAG21
# ---------------------------------------------------------------------------

class TestFeedbackLoopAG21(unittest.TestCase):

    def test_observation_written_after_execution(self):
        """feedback_loop must write to learning_observations.jsonl."""
        from core.orchestrator import feedback_loop
        with _TempRuntime() as rt:
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"):
                feedback_loop.run_loop(
                    run_id="ag21-obs",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            obs_log = rt / "state" / "learning_observations.jsonl"
            self.assertTrue(obs_log.exists(), "learning_observations.jsonl must exist")
            lines = [ln for ln in obs_log.read_text().splitlines() if ln.strip()]
            self.assertGreater(len(lines), 0)

    def test_learning_plane_does_not_block_runtime(self):
        """Even if learning plane raises, run_loop must return a result."""
        from core.orchestrator import feedback_loop
        with _TempRuntime():
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"), \
                 patch("learning.observation_store.append_observation", side_effect=RuntimeError("boom")):
                result = feedback_loop.run_loop(
                    run_id="ag21-safe",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            self.assertIn("decision_id", result)

    def test_pattern_extracted_after_repeated_failures(self):
        """After 3+ FAILED observations, pattern registry should be populated."""
        from core.orchestrator import feedback_loop
        with _TempRuntime() as rt:
            import importlib, core.config, learning.observation_store as obs
            importlib.reload(core.config)
            importlib.reload(obs)
            # Manually inject 3 FAILED observations to simulate history
            for i in range(3):
                obs.append_observation({
                    "run_id": f"hist-{i}",
                    "execution_result": "FAILED",
                    "verifier_status": "FAILED",
                    "policy_verdict": "ALLOW",
                })
            # Now run one more loop cycle — pattern extraction will fire
            with patch("tools.ops.decision_engine.classify_once", return_value="nominal"), \
                 patch("tools.ops.decision_engine.map_signal_to_action", return_value="no_action"):
                feedback_loop.run_loop(
                    run_id="ag21-pattern",
                    operator_status={"ok": True},
                    runtime_status={"ok": True},
                    policy_drift={"drift_count": 0},
                )
            reg = rt / "state" / "pattern_registry.json"
            self.assertTrue(reg.exists())
            data = json.loads(reg.read_text())
            self.assertIsInstance(data, list)
            self.assertGreater(len(data), 0)


if __name__ == "__main__":
    unittest.main()
