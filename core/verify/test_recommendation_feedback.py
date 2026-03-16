"""AG-54: Tests for Runtime Recommendation Feedback Loop.

3 suites, 11 tests:
  Suite 1: Unit tests — correlation and classification logic
  Suite 2: Integration tests
  Suite 3: Safety / feedback-only invariant tests
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _make_runtime(tmp: str) -> str:
    rt = Path(tmp) / "runtime"
    (rt / "state").mkdir(parents=True, exist_ok=True)
    return str(rt)


def _w(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _seed_full_state(state_dir: Path) -> None:
    """Write minimal state for all loaders."""
    # AG-52 governance gate output
    _w(state_dir / "runtime_governance_gate_latest.json", {
        "ts": "2026-03-16T00:00:00Z", "run_id": "gate-001",
        "gated_recommendations": [
            {
                "recommendation_id": "rec-001",
                "governance_class": "HIGH_SENSITIVITY",
                "requires_operator_review": True,
                "recommended_review_level": "GOVERNANCE_REVIEW",
            },
            {
                "recommendation_id": "rec-002",
                "governance_class": "MEDIUM_SENSITIVITY",
                "requires_operator_review": False,
                "recommended_review_level": "STANDARD_REVIEW",
            },
        ],
        "total_count": 2,
    })
    # AG-44 decision queue
    _w(state_dir / "decision_queue_governance_latest.json", {
        "ts": "2026-03-16T00:00:00Z", "open_count": 1,
        "entries": [{"decision_id": "dec-001", "status": "APPROVED", "target_ref": "rec-001"}],
    })
    # AG-45 decision memory
    _w(state_dir / "operator_decision_memory_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "memory_entries": [{"recommendation_id": "rec-001", "pattern": "test"}],
        "pattern_count": 1,
    })
    # Campaign state (mutation check)
    _w(state_dir / "repair_campaign_latest.json",
       {"campaign_id": "camp-001", "status": "OPEN"})


# ---------------------------------------------------------------------------
# Suite 1: Unit tests
# ---------------------------------------------------------------------------

class TestFeedbackUnit(unittest.TestCase):

    def test_correlate_recommendations_with_decisions_detects_followed(self):
        """rec-001 matched to APPROVED decision → FOLLOWED."""
        from runtime.recommendation_feedback import correlate_recommendations_with_decisions
        recs = [{"recommendation_id": "rec-001", "governance_class": "HIGH_SENSITIVITY"}]
        decision_queue = {
            "present": True, "open_count": 1,
            "entries": [{"decision_id": "dec-001", "status": "APPROVED", "target_ref": "rec-001"}],
        }
        history = {"present": True, "memory_entries": [], "inbox_entries": []}

        results = correlate_recommendations_with_decisions(recs, decision_queue, history)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["feedback_class"], "FOLLOWED")
        self.assertEqual(results[0]["recommendation_id"], "rec-001")

    def test_correlate_recommendations_with_decisions_detects_deferred(self):
        """rec-002 in open queue with no matching decision → DEFERRED."""
        from runtime.recommendation_feedback import correlate_recommendations_with_decisions
        recs = [{"recommendation_id": "rec-002", "governance_class": "MEDIUM_SENSITIVITY"}]
        decision_queue = {
            "present": True, "open_count": 1,
            "entries": [],  # no matching entry
        }
        history = {"present": True, "memory_entries": [], "inbox_entries": []}

        results = correlate_recommendations_with_decisions(recs, decision_queue, history)
        self.assertEqual(results[0]["feedback_class"], "DEFERRED")

    def test_classify_feedback_outcome_detects_overridden(self):
        """rec matched to REJECTED decision → OVERRIDDEN."""
        from runtime.recommendation_feedback import classify_feedback_outcome
        rec = {"recommendation_id": "rec-003", "governance_class": "CRITICAL_GOVERNANCE"}
        decision_queue = {
            "present": True, "open_count": 0,
            "entries": [{"decision_id": "dec-003", "status": "REJECTED", "target_ref": "rec-003"}],
        }
        history = {"present": True, "memory_entries": [], "inbox_entries": []}

        result = classify_feedback_outcome(rec, decision_queue, history)
        self.assertEqual(result["feedback_class"], "OVERRIDDEN")

    def test_store_recommendation_feedback_writes_outputs(self):
        """store_recommendation_feedback writes all three required files."""
        from runtime.recommendation_feedback import store_recommendation_feedback
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        try:
            rt = Path(tmp) / "runtime"
            (rt / "state").mkdir(parents=True)
            os.environ["LUKA_RUNTIME_ROOT"] = str(rt)
            report = {
                "ts": "2026-03-16T00:00:00Z", "run_id": "test-run",
                "recommendations_total": 1,
                "feedback_counts": {"FOLLOWED": 1, "DEFERRED": 0, "OVERRIDDEN": 0, "IGNORED": 0, "INCONCLUSIVE": 0},
                "feedback_entries": [{"recommendation_id": "rec-001", "feedback_class": "FOLLOWED"}],
                "gaps": [],
                "evidence_refs": [],
            }
            store_recommendation_feedback(report, str(rt))
            state_dir = rt / "state"
            self.assertTrue((state_dir / "runtime_recommendation_feedback_latest.json").exists())
            self.assertTrue((state_dir / "runtime_recommendation_feedback_index.json").exists())
            self.assertTrue((state_dir / "runtime_recommendation_feedback_log.jsonl").exists())
        finally:
            os.environ.pop("LUKA_RUNTIME_ROOT", None)
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Suite 2: Integration tests
# ---------------------------------------------------------------------------

class TestFeedbackIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        _seed_full_state(Path(self.rt) / "state")
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_recommendation_feedback_generates_outputs(self):
        from runtime.recommendation_feedback import run_recommendation_feedback
        result = run_recommendation_feedback(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("recommendations_total", result)
        self.assertIn("feedback_counts", result)
        state_dir = Path(self.rt) / "state"
        for f in [
            "runtime_recommendation_feedback_latest.json",
            "runtime_recommendation_feedback_index.json",
            "runtime_recommendation_feedback_log.jsonl",
        ]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")

    def test_api_recommendation_feedback_latest_returns_json(self):
        from runtime.recommendation_feedback import run_recommendation_feedback
        run_recommendation_feedback(self.rt)
        from interface.operator.api_recommendation_feedback import recommendation_feedback_latest
        result = asyncio.run(recommendation_feedback_latest())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("latest", result)

    def test_api_recommendation_feedback_index_returns_json(self):
        from runtime.recommendation_feedback import run_recommendation_feedback
        run_recommendation_feedback(self.rt)
        from interface.operator.api_recommendation_feedback import recommendation_feedback_index
        result = asyncio.run(recommendation_feedback_index())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("recommendations_total", result)

    def test_api_recommendation_feedback_run_generates_outputs(self):
        from runtime.recommendation_feedback import run_recommendation_feedback
        result = run_recommendation_feedback(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        state_dir = Path(self.rt) / "state"
        for f in [
            "runtime_recommendation_feedback_latest.json",
            "runtime_recommendation_feedback_index.json",
            "runtime_recommendation_feedback_log.jsonl",
        ]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")


# ---------------------------------------------------------------------------
# Suite 3: Safety / feedback-only invariant tests
# ---------------------------------------------------------------------------

class TestFeedbackSafety(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        _seed_full_state(Path(self.rt) / "state")
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mtime(self, filename: str) -> float | None:
        p = Path(self.rt) / "state" / filename
        return p.stat().st_mtime if p.exists() else None

    def test_recommendation_feedback_does_not_mutate_governance_state(self):
        """Governance and campaign state must not be touched."""
        from runtime.recommendation_feedback import run_recommendation_feedback
        before_gate = self._mtime("runtime_governance_gate_latest.json")
        before_camp = self._mtime("repair_campaign_latest.json")
        run_recommendation_feedback(self.rt)
        self.assertEqual(before_gate, self._mtime("runtime_governance_gate_latest.json"))
        self.assertEqual(before_camp, self._mtime("repair_campaign_latest.json"))

    def test_recommendation_feedback_does_not_execute_repairs(self):
        """No repair execution log must be created."""
        from runtime.recommendation_feedback import run_recommendation_feedback
        run_recommendation_feedback(self.rt)
        self.assertFalse(
            (Path(self.rt) / "state" / "drift_repair_execution_log.jsonl").exists()
        )

    def test_recommendation_feedback_is_feedback_only(self):
        """Result must not contain any mutation confirmation keys."""
        from runtime.recommendation_feedback import run_recommendation_feedback
        result = run_recommendation_feedback(self.rt)
        forbidden = {"repaired", "repair_applied", "governance_mutated",
                     "campaign_mutated", "correction_applied", "decision_approved"}
        for k in forbidden:
            self.assertNotIn(k, result, msg=f"Mutation key found: '{k}'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
