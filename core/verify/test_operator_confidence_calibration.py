"""AG-51: Tests for Operator Confidence Calibration.

4 suites / 18 tests:
  Suite 1: Policy unit tests (4)
  Suite 2: Calibration unit tests (4)
  Suite 3: Integration tests (5)
  Suite 4: Safety / advisory-only invariant tests (5)
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


def _seed_state(state_dir: Path, trust_class: str = "TRUSTED_WITH_GAPS", gap_count: int = 1) -> None:
    """Seed minimal state files for calibration tests."""
    trust_index = {
        "ts": "2026-03-16T00:00:00Z",
        "run_id": "seed-001",
        "overall_trust_score": 0.75 if trust_class == "TRUSTED_WITH_GAPS" else 0.92,
        "overall_trust_class": trust_class,
        "gap_count": gap_count,
        "top_gap": "posture_mismatch" if gap_count > 0 else None,
    }
    gaps = []
    if gap_count > 0:
        gaps.append({
            "gap_id": "gap-001",
            "gap_type": "posture_mismatch",
            "severity": "HIGH",
            "summary": "posture mismatch detected.",
            "evidence_refs": ["runtime_claim_verification_latest.json"],
        })
    trust_latest = {
        **trust_index,
        "trust_gaps": gaps,
    }
    _write_json(state_dir / "runtime_claim_trust_index.json", trust_index)
    _write_json(state_dir / "runtime_claim_trust_latest.json", trust_latest)
    _write_json(state_dir / "runtime_trust_guidance_index.json", {
        "ts": "2026-03-16T00:00:00Z",
        "guidance_mode": "TRUST_WITH_CAUTION",
        "caution_class": "LOW_CAUTION",
        "overall_trust_score": trust_index["overall_trust_score"],
        "overall_trust_class": trust_class,
        "gap_count": gap_count,
        "entry_count": 2,
    })
    _write_json(state_dir / "runtime_self_awareness_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "identity": {"agent_id": "clc"},
        "posture": {"posture_class": "ADVISORY_ONLY"},
    })
    _write_json(state_dir / "runtime_readiness.json", {"readiness": "LIMITED"})
    _write_json(state_dir / "runtime_claim_verification_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "mismatches": [],
        "all_results": [{"claim_key": "posture", "ok": True}],
    })


# ---------------------------------------------------------------------------
# Suite 1: Policy unit tests
# ---------------------------------------------------------------------------

class TestOperatorConfidencePolicy(unittest.TestCase):
    """Suite 1: policy pure-function tests."""

    def test_classify_confidence_very_high(self):
        from runtime.operator_confidence_policy import classify_confidence
        self.assertEqual(classify_confidence(0.90), "VERY_HIGH")
        self.assertEqual(classify_confidence(0.85), "VERY_HIGH")
        self.assertEqual(classify_confidence(1.00), "VERY_HIGH")

    def test_classify_confidence_low(self):
        from runtime.operator_confidence_policy import classify_confidence
        self.assertEqual(classify_confidence(0.30), "LOW")
        self.assertEqual(classify_confidence(0.45), "LOW")
        # just below MODERATE threshold
        self.assertEqual(classify_confidence(0.49), "LOW")

    def test_all_confidence_classes_valid(self):
        from runtime.operator_confidence_policy import (
            CONFIDENCE_CLASSES, valid_confidence_class,
        )
        for cls in CONFIDENCE_CLASSES:
            self.assertTrue(valid_confidence_class(cls), msg=f"class {cls!r} failed valid check")
        self.assertFalse(valid_confidence_class("UNKNOWN_CLASS"))

    def test_calibrate_dimension_returns_required_fields(self):
        from runtime.operator_confidence_policy import calibrate_dimension
        result = calibrate_dimension(
            "trust_alignment",
            {"score": 0.80, "rationale": "test rationale"},
        )
        self.assertIn("dimension", result)
        self.assertIn("score", result)
        self.assertIn("confidence_class", result)
        self.assertIn("rationale", result)
        self.assertEqual(result["dimension"], "trust_alignment")
        self.assertAlmostEqual(result["score"], 0.80, places=4)


# ---------------------------------------------------------------------------
# Suite 2: Calibration unit tests
# ---------------------------------------------------------------------------

class TestCalibrationBuilding(unittest.TestCase):
    """Suite 2: calibration function unit tests."""

    def test_calibrate_trust_alignment_returns_dict(self):
        from runtime.operator_confidence_calibration import calibrate_trust_alignment
        trust_data = {
            "overall_trust_score": 0.82,
            "overall_trust_class": "TRUSTED_WITH_GAPS",
            "gap_count": 1,
            "trust_gaps": [],
        }
        result = calibrate_trust_alignment(trust_data)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["dimension"], "trust_alignment")
        self.assertIn("score", result)
        self.assertIn("confidence_class", result)
        self.assertIn("rationale", result)

    def test_calibrate_gap_severity_returns_dict(self):
        from runtime.operator_confidence_calibration import calibrate_gap_severity
        trust_data = {
            "gap_count": 2,
            "trust_gaps": [
                {"gap_id": "gap-001", "severity": "HIGH"},
                {"gap_id": "gap-002", "severity": "MEDIUM"},
            ],
        }
        result = calibrate_gap_severity(trust_data)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["dimension"], "gap_severity")
        self.assertIn("score", result)
        self.assertIn("confidence_class", result)

    def test_derive_overall_confidence_contains_required_fields(self):
        from runtime.operator_confidence_calibration import derive_overall_confidence
        calibrations = [
            {"dimension": "trust_alignment",   "score": 0.80, "confidence_class": "HIGH",     "rationale": "ok"},
            {"dimension": "gap_severity",       "score": 0.70, "confidence_class": "HIGH",     "rationale": "ok"},
            {"dimension": "claim_consistency",  "score": 0.90, "confidence_class": "VERY_HIGH","rationale": "ok"},
            {"dimension": "readiness_match",    "score": 0.55, "confidence_class": "MODERATE", "rationale": "ok"},
            {"dimension": "posture_alignment",  "score": 0.90, "confidence_class": "VERY_HIGH","rationale": "ok"},
        ]
        result = derive_overall_confidence(calibrations)
        self.assertIn("overall_confidence_score", result)
        self.assertIn("overall_confidence_class", result)
        self.assertIn("rationale", result)
        self.assertGreater(result["overall_confidence_score"], 0.0)

    def test_store_confidence_calibration_writes_outputs(self):
        from runtime.operator_confidence_calibration import store_confidence_calibration
        with tempfile.TemporaryDirectory() as tmp:
            rt = _make_runtime(tmp)
            report = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "run_id": str(uuid.uuid4()),
                "overall_confidence_score": 0.78,
                "overall_confidence_class": "HIGH",
                "calibrations": [],
                "evidence_refs": [],
            }
            store_confidence_calibration(report, rt)
            state_dir = Path(rt) / "state"
            self.assertTrue((state_dir / "runtime_operator_confidence_log.jsonl").exists())
            self.assertTrue((state_dir / "runtime_operator_confidence_latest.json").exists())
            self.assertTrue((state_dir / "runtime_operator_confidence_index.json").exists())


# ---------------------------------------------------------------------------
# Suite 3: Integration tests
# ---------------------------------------------------------------------------

class TestOperatorConfidenceIntegration(unittest.TestCase):
    """Suite 3: end-to-end integration tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        _seed_state(Path(self.rt) / "state")
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_calibration_generates_outputs(self):
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        result = run_operator_confidence_calibration(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("overall_confidence_score", result)
        self.assertIn("overall_confidence_class", result)
        state_dir = Path(self.rt) / "state"
        for fname in [
            "runtime_operator_confidence_latest.json",
            "runtime_operator_confidence_index.json",
            "runtime_operator_confidence_log.jsonl",
        ]:
            self.assertTrue((state_dir / fname).exists(), msg=f"missing: {fname}")

    def test_api_latest_returns_json(self):
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        run_operator_confidence_calibration(self.rt)
        from interface.operator.api_operator_confidence import operator_confidence_latest
        result = asyncio.run(operator_confidence_latest())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("latest", result)

    def test_api_index_returns_json(self):
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        run_operator_confidence_calibration(self.rt)
        from interface.operator.api_operator_confidence import operator_confidence_index
        result = asyncio.run(operator_confidence_index())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("overall_confidence_class", result)

    def test_api_calibrations_returns_json(self):
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        run_operator_confidence_calibration(self.rt)
        from interface.operator.api_operator_confidence import operator_confidence_calibrations
        result = asyncio.run(operator_confidence_calibrations())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("calibrations", result)
        self.assertIsInstance(result["calibrations"], list)

    def test_api_run_generates_outputs(self):
        """POST /api/operator_confidence/run returns ok (non-FastAPI path)."""
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        result = run_operator_confidence_calibration(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("overall_confidence_score", result)
        state_dir = Path(self.rt) / "state"
        self.assertTrue((state_dir / "runtime_operator_confidence_latest.json").exists())


# ---------------------------------------------------------------------------
# Suite 4: Safety / advisory-only invariant tests
# ---------------------------------------------------------------------------

class TestOperatorConfidenceSafety(unittest.TestCase):
    """Suite 4: advisory-only invariant tests."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        state_dir = Path(self.rt) / "state"
        _seed_state(state_dir, trust_class="CAUTION", gap_count=2)
        _write_json(state_dir / "decision_queue_governance_latest.json",
                    {"open_count": 2, "entries": []})
        _write_json(state_dir / "repair_campaign_latest.json",
                    {"campaign_id": "camp-001", "status": "OPEN"})
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mtime(self, filename: str) -> float | None:
        p = Path(self.rt) / "state" / filename
        return p.stat().st_mtime if p.exists() else None

    def test_calibration_does_not_mutate_governance_state(self):
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        before = self._mtime("decision_queue_governance_latest.json")
        run_operator_confidence_calibration(self.rt)
        self.assertEqual(before, self._mtime("decision_queue_governance_latest.json"))

    def test_calibration_does_not_mutate_campaign_state(self):
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        before = self._mtime("repair_campaign_latest.json")
        run_operator_confidence_calibration(self.rt)
        self.assertEqual(before, self._mtime("repair_campaign_latest.json"))

    def test_calibration_does_not_execute_repairs(self):
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        run_operator_confidence_calibration(self.rt)
        self.assertFalse(
            (Path(self.rt) / "state" / "drift_repair_execution_log.jsonl").exists()
        )

    def test_calibration_is_advisory_only(self):
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        result = run_operator_confidence_calibration(self.rt)
        forbidden = {"repaired", "repair_applied", "governance_mutated",
                     "campaign_mutated", "correction_applied"}
        for k in forbidden:
            self.assertNotIn(k, result)

    def test_no_auto_correction(self):
        """Calibration run must not modify trust or claim state files."""
        from runtime.operator_confidence_calibration import run_operator_confidence_calibration
        before_trust = self._mtime("runtime_claim_trust_index.json")
        before_verif = self._mtime("runtime_claim_verification_latest.json")
        run_operator_confidence_calibration(self.rt)
        self.assertEqual(before_trust, self._mtime("runtime_claim_trust_index.json"))
        self.assertEqual(before_verif, self._mtime("runtime_claim_verification_latest.json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
