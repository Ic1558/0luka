"""AG-50: Tests for Runtime Trust-Aware Operator Guidance.

4 suites:
  Suite 1: Policy unit tests
  Suite 2: Guidance unit tests
  Suite 3: Integration tests
  Suite 4: Safety / advisory-only invariant tests
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


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _seed_trust_state(state_dir: Path, trust_class: str = "TRUSTED_WITH_GAPS", gap_count: int = 1) -> None:
    index = {
        "ts": "2026-03-16T00:00:00Z", "run_id": "smoke-001",
        "overall_trust_score": 0.82 if trust_class == "TRUSTED_WITH_GAPS" else 0.95,
        "overall_trust_class": trust_class,
        "claim_groups": {"identity": "HIGH_TRUST", "readiness": trust_class, "posture": "CAUTION"},
        "gap_count": gap_count,
        "top_gap": "posture_mismatch" if gap_count > 0 else None,
    }
    _write_json(state_dir / "runtime_claim_trust_index.json", index)

    gaps = []
    if gap_count > 0:
        gaps.append({"gap_id": "gap-001", "gap_type": "posture_mismatch",
                     "severity": "HIGH", "summary": "posture claimed ADVISORY_ONLY contradicts evidence.",
                     "evidence_refs": ["runtime_claim_verification_latest.json"]})
    latest = {**index, "trust_gaps": gaps, "overall": index,
              "identity_trust": {"trust_score": 1.0}, "readiness_trust": {"trust_score": 0.82},
              "posture_trust": {"trust_score": 0.5}, "caution_notes": [], "evidence_refs": []}
    _write_json(state_dir / "runtime_claim_trust_latest.json", latest)
    _write_json(state_dir / "runtime_self_awareness_latest.json",
                {"ts": "2026-03-16T00:00:00Z", "identity": {}, "posture": {}})
    _write_json(state_dir / "runtime_readiness.json", {"readiness": "LIMITED"})
    _write_json(state_dir / "runtime_claim_verification_latest.json",
                {"ts": "2026-03-16T00:00:00Z", "mismatches": [], "all_results": []})


# ---------------------------------------------------------------------------
# Suite 1: Policy unit tests
# ---------------------------------------------------------------------------

class TestTrustGuidancePolicy(unittest.TestCase):

    def setUp(self):
        from runtime.trust_guidance_policy import (
            classify_caution, guidance_mode_for_trust_class,
            valid_guidance_mode, valid_caution_class, GUIDANCE_MODES, CAUTION_CLASSES,
        )
        self.classify_caution             = classify_caution
        self.guidance_mode_for_trust_class = guidance_mode_for_trust_class
        self.valid_guidance_mode          = valid_guidance_mode
        self.valid_caution_class          = valid_caution_class
        self.GUIDANCE_MODES               = GUIDANCE_MODES
        self.CAUTION_CLASSES              = CAUTION_CLASSES

    def test_guidance_mode_for_high_trust(self):
        self.assertEqual(self.guidance_mode_for_trust_class("HIGH_TRUST"), "TRUST_ALIGNED")

    def test_guidance_mode_for_untrusted(self):
        self.assertEqual(self.guidance_mode_for_trust_class("UNTRUSTED"), "CLAIM_MISMATCH_ALERT")

    def test_classify_caution_no_caution(self):
        self.assertEqual(self.classify_caution(0.95, 0), "NO_CAUTION")

    def test_classify_caution_high(self):
        result = self.classify_caution(0.30, 5)
        self.assertEqual(result, "HIGH_CAUTION")

    def test_classify_caution_critical(self):
        self.assertEqual(self.classify_caution(0.10, 10), "CRITICAL_CAUTION")

    def test_all_guidance_modes_valid(self):
        for mode in self.GUIDANCE_MODES:
            self.assertTrue(self.valid_guidance_mode(mode))

    def test_all_caution_classes_valid(self):
        for cls in self.CAUTION_CLASSES:
            self.assertTrue(self.valid_caution_class(cls))


# ---------------------------------------------------------------------------
# Suite 2: Guidance unit tests
# ---------------------------------------------------------------------------

class TestGuidanceBuilding(unittest.TestCase):

    def test_derive_guidance_mode_trusted_with_gaps(self):
        from runtime.trust_aware_guidance import derive_guidance_mode
        trust_data = {"overall_trust_class": "TRUSTED_WITH_GAPS", "overall_trust_score": 0.80}
        self.assertEqual(derive_guidance_mode(trust_data), "TRUST_WITH_CAUTION")

    def test_derive_guidance_mode_no_trust_class(self):
        from runtime.trust_aware_guidance import derive_guidance_mode
        self.assertEqual(derive_guidance_mode({}), "CLAIM_MISMATCH_ALERT")

    def test_build_guidance_entries_contains_overall(self):
        from runtime.trust_aware_guidance import build_guidance_entries
        trust_data = {
            "overall_trust_class": "HIGH_TRUST", "overall_trust_score": 0.95,
            "gap_count": 0, "trust_gaps": [],
        }
        entries = build_guidance_entries(trust_data, {}, {"mismatches": []})
        self.assertGreater(len(entries), 0)
        ids = [e["guidance_id"] for e in entries]
        self.assertIn("guidance-overall", ids)

    def test_build_guidance_entries_gap_entries_present(self):
        from runtime.trust_aware_guidance import build_guidance_entries
        trust_data = {
            "overall_trust_class": "CAUTION", "overall_trust_score": 0.55,
            "gap_count": 1,
            "trust_gaps": [{"gap_id": "gap-001", "gap_type": "posture_mismatch",
                             "severity": "HIGH", "summary": "test gap", "evidence_refs": []}],
        }
        entries = build_guidance_entries(trust_data, {}, {"mismatches": []})
        gap_entries = [e for e in entries if e.get("dimension") == "gap"]
        self.assertGreater(len(gap_entries), 0)
        self.assertEqual(gap_entries[0]["guidance_mode"], "HIGH_SCRUTINY")

    def test_store_trust_guidance_writes_outputs(self):
        from runtime.trust_aware_guidance import store_trust_guidance
        import uuid, time
        with tempfile.TemporaryDirectory() as tmp:
            rt = _make_runtime(tmp)
            report = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "run_id": str(uuid.uuid4()),
                "guidance_mode": "TRUST_ALIGNED", "caution_class": "NO_CAUTION",
                "overall_trust_score": 0.95, "overall_trust_class": "HIGH_TRUST",
                "gap_count": 0, "guidance_entries": [],
                "description": "ok", "evidence_refs": [],
            }
            store_trust_guidance(report, rt)
            state_dir = Path(rt) / "state"
            self.assertTrue((state_dir / "runtime_trust_guidance_log.jsonl").exists())
            self.assertTrue((state_dir / "runtime_trust_guidance_latest.json").exists())
            self.assertTrue((state_dir / "runtime_trust_guidance_index.json").exists())


# ---------------------------------------------------------------------------
# Suite 3: Integration tests
# ---------------------------------------------------------------------------

class TestTrustGuidanceIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        _seed_trust_state(Path(self.rt) / "state")
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_trust_aware_guidance_generates_outputs(self):
        from runtime.trust_aware_guidance import run_trust_aware_guidance
        result = run_trust_aware_guidance(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("guidance_mode", result)
        self.assertIn("caution_class", result)
        state_dir = Path(self.rt) / "state"
        for f in ["runtime_trust_guidance_latest.json",
                  "runtime_trust_guidance_index.json",
                  "runtime_trust_guidance_log.jsonl"]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")

    def test_api_trust_guidance_latest_returns_json(self):
        from runtime.trust_aware_guidance import run_trust_aware_guidance
        run_trust_aware_guidance(self.rt)
        from interface.operator.api_trust_guidance import trust_guidance_latest
        result = asyncio.run(trust_guidance_latest())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("latest", result)

    def test_api_trust_guidance_index_returns_json(self):
        from runtime.trust_aware_guidance import run_trust_aware_guidance
        run_trust_aware_guidance(self.rt)
        from interface.operator.api_trust_guidance import trust_guidance_index
        result = asyncio.run(trust_guidance_index())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("guidance_mode", result)

    def test_api_trust_guidance_entries_returns_json(self):
        from runtime.trust_aware_guidance import run_trust_aware_guidance
        run_trust_aware_guidance(self.rt)
        from interface.operator.api_trust_guidance import trust_guidance_entries
        result = asyncio.run(trust_guidance_entries())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("guidance_entries", result)


# ---------------------------------------------------------------------------
# Suite 4: Safety / advisory-only invariant tests
# ---------------------------------------------------------------------------

class TestTrustGuidanceSafety(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        state_dir = Path(self.rt) / "state"
        _seed_trust_state(state_dir, trust_class="CAUTION", gap_count=2)
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

    def test_guidance_does_not_mutate_governance_state(self):
        from runtime.trust_aware_guidance import run_trust_aware_guidance
        before = self._mtime("decision_queue_governance_latest.json")
        run_trust_aware_guidance(self.rt)
        self.assertEqual(before, self._mtime("decision_queue_governance_latest.json"))

    def test_guidance_does_not_mutate_campaign_state(self):
        from runtime.trust_aware_guidance import run_trust_aware_guidance
        before = self._mtime("repair_campaign_latest.json")
        run_trust_aware_guidance(self.rt)
        self.assertEqual(before, self._mtime("repair_campaign_latest.json"))

    def test_guidance_does_not_execute_repairs(self):
        from runtime.trust_aware_guidance import run_trust_aware_guidance
        run_trust_aware_guidance(self.rt)
        self.assertFalse(
            (Path(self.rt) / "state" / "drift_repair_execution_log.jsonl").exists()
        )

    def test_guidance_is_advisory_only(self):
        from runtime.trust_aware_guidance import run_trust_aware_guidance
        result = run_trust_aware_guidance(self.rt)
        forbidden = {"repaired", "repair_applied", "governance_mutated",
                     "campaign_mutated", "correction_applied"}
        for k in forbidden:
            self.assertNotIn(k, result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
