"""AG-53: Tests for Operator Decision Flow Integrity Layer.

3 suites, 10 tests:
  Suite 1: Unit tests — lifecycle validation logic
  Suite 2: Integration tests
  Suite 3: Safety / validation-only invariant tests
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
                "target_ref": "guidance-overall",
                "governance_class": "HIGH_SENSITIVITY",
                "requires_operator_review": True,
                "recommended_review_level": "GOVERNANCE_REVIEW",
                "confidence_class": "MODERATE",
                "trust_class": "TRUSTED_WITH_GAPS",
                "evidence_refs": [],
            }
        ],
        "total_count": 1, "high_sensitivity": 1, "critical": 0,
        "governance_summary": {"HIGH_SENSITIVITY": 1},
    })
    # AG-44 decision queue
    _w(state_dir / "decision_queue_governance_latest.json", {
        "ts": "2026-03-16T00:00:00Z", "open_count": 1,
        "entries": [{"decision_id": "dec-001", "status": "OPEN"}],
    })
    # AG-45 decision memory
    _w(state_dir / "operator_decision_memory_latest.json", {
        "ts": "2026-03-16T00:00:00Z", "memory_entries": [{"pattern": "test"}],
        "pattern_count": 1,
    })
    # AG-50 trust guidance
    _w(state_dir / "runtime_trust_guidance_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "guidance_mode": "TRUST_WITH_CAUTION", "guidance_entries": [
            {"guidance_id": "guidance-overall", "dimension": "overall",
             "guidance_mode": "TRUST_WITH_CAUTION", "caution_class": "LOW_CAUTION",
             "trust_score": 0.82, "trust_class": "TRUSTED_WITH_GAPS",
             "description": "ok", "evidence_refs": [], "override_type": "NO_OVERRIDE"},
        ],
    })
    # Campaign state (for mutation test)
    _w(state_dir / "repair_campaign_latest.json",
       {"campaign_id": "camp-001", "status": "OPEN"})


# ---------------------------------------------------------------------------
# Suite 1: Unit tests
# ---------------------------------------------------------------------------

class TestIntegrityUnit(unittest.TestCase):

    def test_integrity_valid_chain(self):
        """A fully-gated recommendation with all state present → valid lifecycle."""
        from runtime.operator_decision_integrity import validate_recommendation_lifecycle
        rec = {
            "recommendation_id": "rec-001",
            "governance_class": "HIGH_SENSITIVITY",
            "requires_operator_review": True,
            "recommended_review_level": "GOVERNANCE_REVIEW",
        }
        operator_queue  = {"present": True, "entries": [], "entry_ids": set()}
        decision_queue  = {"present": True, "open_count": 1, "entries": []}
        decision_memory = {"present": True, "memory_entries": [], "pattern_count": 0}

        result = validate_recommendation_lifecycle(rec, operator_queue, decision_queue, decision_memory)
        self.assertTrue(result["governance_gate"])
        self.assertTrue(result["valid_lifecycle"])
        self.assertFalse(result["broken_chain"])

    def test_integrity_detects_missing_queue(self):
        """No queue presence → missing_steps includes operator_queue."""
        from runtime.operator_decision_integrity import validate_recommendation_lifecycle
        rec = {
            "recommendation_id": "rec-002",
            "governance_class": "MEDIUM_SENSITIVITY",
            "requires_operator_review": False,
            "recommended_review_level": "STANDARD_REVIEW",
        }
        operator_queue  = {"present": False, "entries": [], "entry_ids": set()}
        decision_queue  = {"present": False, "open_count": 0, "entries": []}
        decision_memory = {"present": True, "memory_entries": [], "pattern_count": 0}

        result = validate_recommendation_lifecycle(rec, operator_queue, decision_queue, decision_memory)
        self.assertTrue(result["broken_chain"])
        self.assertIn("operator_queue", result["missing_steps"])

    def test_integrity_detects_missing_memory(self):
        """No decision memory → missing_steps includes memory_write."""
        from runtime.operator_decision_integrity import validate_recommendation_lifecycle
        rec = {
            "recommendation_id": "rec-003",
            "governance_class": "LOW_SENSITIVITY",
            "requires_operator_review": False,
            "recommended_review_level": "NO_REVIEW",
        }
        operator_queue  = {"present": True, "entries": [], "entry_ids": set()}
        decision_queue  = {"present": True, "open_count": 0, "entries": []}
        decision_memory = {"present": False, "memory_entries": [], "pattern_count": 0}

        result = validate_recommendation_lifecycle(rec, operator_queue, decision_queue, decision_memory)
        self.assertTrue(result["broken_chain"])
        self.assertIn("memory_write", result["missing_steps"])

    def test_integrity_classification_required(self):
        """Recommendation missing governance_class → governance_gate=False."""
        from runtime.operator_decision_integrity import validate_recommendation_lifecycle
        rec = {"recommendation_id": "rec-004"}  # no governance metadata
        operator_queue  = {"present": True, "entries": [], "entry_ids": set()}
        decision_queue  = {"present": True, "open_count": 1, "entries": []}
        decision_memory = {"present": True, "memory_entries": [], "pattern_count": 0}

        result = validate_recommendation_lifecycle(rec, operator_queue, decision_queue, decision_memory)
        self.assertFalse(result["governance_gate"])
        self.assertTrue(result["broken_chain"])


# ---------------------------------------------------------------------------
# Suite 2: Integration tests
# ---------------------------------------------------------------------------

class TestIntegrityIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        _seed_full_state(Path(self.rt) / "state")
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_operator_integrity_outputs_files(self):
        from runtime.operator_decision_integrity import run_operator_decision_integrity
        result = run_operator_decision_integrity(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("recommendations_checked", result)
        self.assertIn("valid_lifecycle", result)
        self.assertIn("broken_chain", result)
        state_dir = Path(self.rt) / "state"
        for f in [
            "runtime_operator_decision_integrity_latest.json",
            "runtime_operator_decision_integrity_index.json",
            "runtime_operator_decision_integrity_log.jsonl",
        ]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")

    def test_api_operator_integrity_latest(self):
        from runtime.operator_decision_integrity import run_operator_decision_integrity
        run_operator_decision_integrity(self.rt)
        from interface.operator.api_operator_integrity import operator_integrity_latest
        result = asyncio.run(operator_integrity_latest())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("latest", result)

    def test_api_operator_integrity_index(self):
        from runtime.operator_decision_integrity import run_operator_decision_integrity
        run_operator_decision_integrity(self.rt)
        from interface.operator.api_operator_integrity import operator_integrity_index
        result = asyncio.run(operator_integrity_index())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("recommendations_checked", result)

    def test_api_operator_integrity_broken(self):
        from runtime.operator_decision_integrity import run_operator_decision_integrity
        run_operator_decision_integrity(self.rt)
        from interface.operator.api_operator_integrity import operator_integrity_broken
        result = asyncio.run(operator_integrity_broken())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("broken_results", result)

    def test_api_operator_integrity_run(self):
        """Integration: run produces all three output files."""
        from runtime.operator_decision_integrity import run_operator_decision_integrity
        result = run_operator_decision_integrity(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        state_dir = Path(self.rt) / "state"
        for f in [
            "runtime_operator_decision_integrity_latest.json",
            "runtime_operator_decision_integrity_index.json",
            "runtime_operator_decision_integrity_log.jsonl",
        ]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")


# ---------------------------------------------------------------------------
# Suite 3: Safety / validation-only invariant tests
# ---------------------------------------------------------------------------

class TestIntegritySafety(unittest.TestCase):

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

    def test_integrity_does_not_mutate_state(self):
        """Governance state must not be touched."""
        from runtime.operator_decision_integrity import run_operator_decision_integrity
        before_gov  = self._mtime("decision_queue_governance_latest.json")
        before_camp = self._mtime("repair_campaign_latest.json")
        run_operator_decision_integrity(self.rt)
        self.assertEqual(before_gov,  self._mtime("decision_queue_governance_latest.json"))
        self.assertEqual(before_camp, self._mtime("repair_campaign_latest.json"))

    def test_integrity_does_not_execute_repairs(self):
        """No repair execution log must be created."""
        from runtime.operator_decision_integrity import run_operator_decision_integrity
        run_operator_decision_integrity(self.rt)
        self.assertFalse(
            (Path(self.rt) / "state" / "drift_repair_execution_log.jsonl").exists()
        )

    def test_integrity_is_validation_only(self):
        """Result must not contain any mutation confirmation keys."""
        from runtime.operator_decision_integrity import run_operator_decision_integrity
        result = run_operator_decision_integrity(self.rt)
        forbidden = {"repaired", "repair_applied", "governance_mutated",
                     "campaign_mutated", "correction_applied", "decision_approved"}
        for k in forbidden:
            self.assertNotIn(k, result, msg=f"Mutation key found: '{k}'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
