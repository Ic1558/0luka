"""AG-52: Tests for Runtime Recommendation Governance Gate.

3 suites / 11 tests:
  Suite 1: Unit tests (4)
  Suite 2: Integration tests (4)
  Suite 3: Safety / advisory-only invariant tests (3)
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _make_runtime(tmp: str) -> str:
    rt = Path(tmp) / "runtime"
    (rt / "state").mkdir(parents=True, exist_ok=True)
    return str(rt)


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _seed_state(
    state_dir: Path,
    trust_class: str = "TRUSTED_WITH_GAPS",
    confidence_class: str = "MODERATE",
    gap_count: int = 1,
) -> None:
    """Seed minimal state files for governance gate tests."""
    _write_json(state_dir / "runtime_trust_guidance_index.json", {
        "ts": "2026-03-16T00:00:00Z",
        "guidance_mode": "TRUST_WITH_CAUTION",
        "caution_class": "LOW_CAUTION",
        "overall_trust_score": 0.75,
        "overall_trust_class": trust_class,
        "gap_count": gap_count,
        "entry_count": 2,
    })
    guidance_entries = [
        {
            "guidance_id": "guidance-overall",
            "dimension": "overall",
            "guidance_mode": "TRUST_WITH_CAUTION",
            "caution_class": "LOW_CAUTION",
            "trust_score": 0.75,
            "trust_class": trust_class,
            "description": "review gaps",
            "evidence_refs": ["runtime_claim_trust_index.json"],
            "override_type": "NO_OVERRIDE",
        },
        {
            "guidance_id": "guidance-gap-001",
            "dimension": "gap",
            "guidance_mode": "HIGH_SCRUTINY",
            "caution_class": "HIGH_CAUTION",
            "gap_type": "posture_mismatch",
            "gap_severity": "HIGH",
            "summary": "posture mismatch detected",
            "evidence_refs": ["runtime_claim_verification_latest.json"],
            "override_type": "GAP_SEVERITY_OVERRIDE",
        },
    ]
    _write_json(state_dir / "runtime_trust_guidance_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "guidance_mode": "TRUST_WITH_CAUTION",
        "caution_class": "LOW_CAUTION",
        "overall_trust_score": 0.75,
        "overall_trust_class": trust_class,
        "gap_count": gap_count,
        "guidance_entries": guidance_entries,
        "description": "review",
        "evidence_refs": [],
    })
    _write_json(state_dir / "runtime_operator_confidence_index.json", {
        "ts": "2026-03-16T00:00:00Z",
        "run_id": "seed-conf-001",
        "overall_confidence_score": 0.65,
        "overall_confidence_class": confidence_class,
        "dimension_count": 5,
    })
    _write_json(state_dir / "decision_queue_governance_latest.json",
                {"open_count": 1, "entries": []})


# ---------------------------------------------------------------------------
# Suite 1: Unit tests
# ---------------------------------------------------------------------------

class TestGovernanceGateUnit(unittest.TestCase):
    """Suite 1: pure-function unit tests."""

    def test_classify_governance_sensitivity_returns_expected_class(self):
        from runtime.recommendation_governance_gate import classify_governance_sensitivity
        rec          = {"guidance_id": "guidance-overall", "caution_class": "LOW_CAUTION"}
        trust_data   = {"overall_trust_class": "HIGH_TRUST",     "gap_count": 0}
        confidence   = {"overall_confidence_class": "VERY_HIGH"}
        result = classify_governance_sensitivity(rec, trust_data, confidence)
        self.assertIn(result, ["LOW_SENSITIVITY", "MEDIUM_SENSITIVITY", "HIGH_SENSITIVITY", "CRITICAL_GOVERNANCE"])

    def test_attach_governance_gate_contains_required_fields(self):
        from runtime.recommendation_governance_gate import attach_governance_gate
        rec          = {"guidance_id": "rec-001", "caution_class": "LOW_CAUTION"}
        trust_data   = {"overall_trust_class": "TRUSTED_WITH_GAPS", "gap_count": 1}
        confidence   = {"overall_confidence_class": "MODERATE"}
        gate = attach_governance_gate(rec, "HIGH_SENSITIVITY", trust_data, confidence)
        required = [
            "recommendation_id", "target_ref", "governance_class",
            "requires_operator_review", "recommended_review_level",
            "confidence_class", "trust_class", "evidence_refs",
        ]
        for field in required:
            self.assertIn(field, gate, msg=f"missing field: {field!r}")
        self.assertEqual(gate["governance_class"], "HIGH_SENSITIVITY")
        self.assertTrue(gate["requires_operator_review"])

    def test_generate_governance_gated_recommendations_contains_required_fields(self):
        from runtime.recommendation_governance_gate import generate_governance_gated_recommendations
        recs = [
            {"guidance_id": "guidance-overall", "caution_class": "LOW_CAUTION",
             "guidance_mode": "TRUST_WITH_CAUTION"},
            {"guidance_id": "guidance-gap-001", "caution_class": "HIGH_CAUTION",
             "guidance_mode": "HIGH_SCRUTINY"},
        ]
        trust_data = {"overall_trust_class": "TRUSTED_WITH_GAPS", "gap_count": 1}
        confidence = {"overall_confidence_class": "MODERATE"}
        gated = generate_governance_gated_recommendations(recs, trust_data, confidence)
        self.assertEqual(len(gated), 2)
        for g in gated:
            self.assertIn("governance_class", g)
            self.assertIn("requires_operator_review", g)
            self.assertIn("recommended_review_level", g)

    def test_store_governance_gate_outputs_writes_files(self):
        from runtime.recommendation_governance_gate import store_governance_gate_outputs
        with tempfile.TemporaryDirectory() as tmp:
            rt = _make_runtime(tmp)
            report = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "run_id": str(uuid.uuid4()),
                "gated_recommendations": [],
                "total_count": 0,
                "high_sensitivity": 0,
                "critical": 0,
                "governance_summary": {
                    "LOW_SENSITIVITY": 0, "MEDIUM_SENSITIVITY": 0,
                    "HIGH_SENSITIVITY": 0, "CRITICAL_GOVERNANCE": 0,
                },
            }
            store_governance_gate_outputs(report, rt)
            state_dir = Path(rt) / "state"
            self.assertTrue((state_dir / "runtime_governance_gate_log.jsonl").exists())
            self.assertTrue((state_dir / "runtime_governance_gate_latest.json").exists())
            self.assertTrue((state_dir / "runtime_governance_gate_index.json").exists())


# ---------------------------------------------------------------------------
# Suite 2: Integration tests
# ---------------------------------------------------------------------------

class TestGovernanceGateIntegration(unittest.TestCase):
    """Suite 2: end-to-end integration tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        _seed_state(Path(self.rt) / "state")
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_recommendation_governance_gate_generates_outputs(self):
        from runtime.recommendation_governance_gate import run_recommendation_governance_gate
        result = run_recommendation_governance_gate(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("total_count", result)
        self.assertIn("high_sensitivity", result)
        state_dir = Path(self.rt) / "state"
        for fname in [
            "runtime_governance_gate_latest.json",
            "runtime_governance_gate_index.json",
            "runtime_governance_gate_log.jsonl",
        ]:
            self.assertTrue((state_dir / fname).exists(), msg=f"missing: {fname}")

    def test_api_governance_gate_latest_returns_json(self):
        from runtime.recommendation_governance_gate import run_recommendation_governance_gate
        run_recommendation_governance_gate(self.rt)
        from interface.operator.api_governance_gate import governance_gate_latest
        result = asyncio.run(governance_gate_latest())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("latest", result)

    def test_api_governance_gate_index_returns_json(self):
        from runtime.recommendation_governance_gate import run_recommendation_governance_gate
        run_recommendation_governance_gate(self.rt)
        from interface.operator.api_governance_gate import governance_gate_index
        result = asyncio.run(governance_gate_index())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("total_count", result)
        self.assertIn("governance_summary", result)

    def test_api_governance_gate_run_generates_outputs(self):
        """Trigger gate run via public function (non-FastAPI path)."""
        from runtime.recommendation_governance_gate import run_recommendation_governance_gate
        result = run_recommendation_governance_gate(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        state_dir = Path(self.rt) / "state"
        self.assertTrue((state_dir / "runtime_governance_gate_latest.json").exists())
        # Verify gated recommendations present
        data = json.loads((state_dir / "runtime_governance_gate_latest.json").read_text())
        self.assertIn("gated_recommendations", data)


# ---------------------------------------------------------------------------
# Suite 3: Safety / advisory-only invariant tests
# ---------------------------------------------------------------------------

class TestGovernanceGateSafety(unittest.TestCase):
    """Suite 3: advisory-only invariant tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        state_dir = Path(self.rt) / "state"
        _seed_state(state_dir, trust_class="CAUTION", confidence_class="LOW", gap_count=2)
        _write_json(state_dir / "repair_campaign_latest.json",
                    {"campaign_id": "camp-001", "status": "OPEN"})
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mtime(self, filename: str) -> float | None:
        p = Path(self.rt) / "state" / filename
        return p.stat().st_mtime if p.exists() else None

    def test_governance_gate_does_not_mutate_governance_state(self):
        from runtime.recommendation_governance_gate import run_recommendation_governance_gate
        before = self._mtime("decision_queue_governance_latest.json")
        run_recommendation_governance_gate(self.rt)
        self.assertEqual(before, self._mtime("decision_queue_governance_latest.json"))

    def test_governance_gate_does_not_execute_repairs(self):
        from runtime.recommendation_governance_gate import run_recommendation_governance_gate
        run_recommendation_governance_gate(self.rt)
        self.assertFalse(
            (Path(self.rt) / "state" / "drift_repair_execution_log.jsonl").exists()
        )

    def test_governance_gate_is_classification_only(self):
        from runtime.recommendation_governance_gate import run_recommendation_governance_gate
        result = run_recommendation_governance_gate(self.rt)
        forbidden = {"repaired", "repair_applied", "governance_mutated",
                     "campaign_mutated", "correction_applied"}
        for k in forbidden:
            self.assertNotIn(k, result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
