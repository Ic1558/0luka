"""AG-49: Tests for Runtime Claim Trust Index Layer.

4 suites, 15 tests:
  Suite 1: Policy unit tests
  Suite 2: Trust scoring unit tests
  Suite 3: Integration tests
  Suite 4: Safety / advisory-only invariant tests
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _make_runtime(tmp: str) -> str:
    """Create minimal runtime directory tree."""
    rt = Path(tmp) / "runtime"
    (rt / "state").mkdir(parents=True, exist_ok=True)
    return str(rt)


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_verification_latest(state_dir: Path, *, all_verified: bool = True) -> None:
    """Write a minimal claim verification latest file."""
    verdict = "VERIFIED" if all_verified else "INCONSISTENT"
    payload = {
        "ts": "2026-03-16T00:00:00Z",
        "run_id": "smoke-001",
        "all_results": [
            {"claim_class": "identity",  "claim_key": "system_identity",
             "claimed_value": "Supervised Agentic Runtime Platform",
             "observed_value": "Supervised Agentic Runtime Platform",
             "verdict": "VERIFIED", "evidence_refs": []},
            {"claim_class": "readiness", "claim_key": "readiness",
             "claimed_value": "LIMITED",
             "observed_value": None,
             "verdict": verdict, "evidence_refs": []},
            {"claim_class": "posture",   "claim_key": "governance_posture",
             "claimed_value": "ADVISORY_ONLY",
             "observed_value": None,
             "verdict": verdict, "evidence_refs": []},
        ],
        "identity_results":  [
            {"claim_class": "identity",  "claim_key": "system_identity",
             "claimed_value": "Supervised Agentic Runtime Platform",
             "observed_value": "Supervised Agentic Runtime Platform",
             "verdict": "VERIFIED", "evidence_refs": []},
        ],
        "readiness_results": [
            {"claim_class": "readiness", "claim_key": "readiness",
             "claimed_value": "LIMITED",
             "observed_value": None,
             "verdict": verdict, "evidence_refs": []},
        ],
        "posture_results":   [
            {"claim_class": "posture",   "claim_key": "governance_posture",
             "claimed_value": "ADVISORY_ONLY",
             "observed_value": None,
             "verdict": verdict, "evidence_refs": []},
        ],
        "mismatches": [],
    }
    _write_json(state_dir / "runtime_claim_verification_latest.json", payload)
    _write_json(state_dir / "runtime_claim_verdicts.json", {})


def _make_self_awareness_latest(state_dir: Path) -> None:
    payload = {
        "ts": "2026-03-16T00:00:00Z",
        "identity": {"system_identity": "Supervised Agentic Runtime Platform",
                     "runtime_role": "governed execution + supervised repair + advisory intelligence"},
        "posture":  {"governance_posture": "ADVISORY_ONLY"},
    }
    _write_json(state_dir / "runtime_self_awareness_latest.json", payload)
    _write_json(state_dir / "runtime_readiness.json",
                {"readiness": "LIMITED", "active_capability_count": 0})


# ---------------------------------------------------------------------------
# Suite 1: Policy unit tests
# ---------------------------------------------------------------------------

class TestClaimTrustPolicy(unittest.TestCase):

    def setUp(self):
        from runtime.claim_trust_policy import (
            classify_trust, weighted_claim_group_score, valid_trust_class, TRUST_CLASSES,
        )
        self.classify_trust           = classify_trust
        self.weighted_claim_group_score = weighted_claim_group_score
        self.valid_trust_class        = valid_trust_class
        self.TRUST_CLASSES            = TRUST_CLASSES

    def test_classify_trust_high_trust(self):
        self.assertEqual(self.classify_trust(0.95), "HIGH_TRUST")
        self.assertEqual(self.classify_trust(0.90), "HIGH_TRUST")

    def test_classify_trust_trusted_with_gaps(self):
        self.assertEqual(self.classify_trust(0.80), "TRUSTED_WITH_GAPS")
        self.assertEqual(self.classify_trust(0.70), "TRUSTED_WITH_GAPS")

    def test_classify_trust_caution(self):
        self.assertEqual(self.classify_trust(0.60), "CAUTION")
        self.assertEqual(self.classify_trust(0.50), "CAUTION")

    def test_classify_trust_untrusted(self):
        self.assertEqual(self.classify_trust(0.0), "UNTRUSTED")
        self.assertEqual(self.classify_trust(0.10), "UNTRUSTED")

    def test_weighted_claim_group_score_all_verified(self):
        score = self.weighted_claim_group_score(5, 0, 0, 0)
        self.assertAlmostEqual(score, 1.0)

    def test_weighted_claim_group_score_empty(self):
        score = self.weighted_claim_group_score(0, 0, 0, 0)
        self.assertEqual(score, 0.0)

    def test_valid_trust_class_known(self):
        for tc in self.TRUST_CLASSES:
            self.assertTrue(self.valid_trust_class(tc))

    def test_valid_trust_class_unknown(self):
        self.assertFalse(self.valid_trust_class("SUPREME_TRUST"))


# ---------------------------------------------------------------------------
# Suite 2: Trust scoring unit tests
# ---------------------------------------------------------------------------

class TestTrustScoring(unittest.TestCase):

    def test_score_identity_trust_returns_high_trust_when_all_verified(self):
        from runtime.claim_trust_index import score_identity_trust
        verification_data = {
            "identity_results": [
                {"verdict": "VERIFIED"},
                {"verdict": "VERIFIED"},
                {"verdict": "VERIFIED"},
            ]
        }
        result = score_identity_trust(verification_data)
        self.assertEqual(result["claim_group"], "identity")
        self.assertGreaterEqual(result["trust_score"], 0.90)
        self.assertEqual(result["trust_class"], "HIGH_TRUST")
        self.assertIn("verified", result)
        self.assertIn("total", result)

    def test_score_readiness_trust_returns_trusted_with_gaps_when_unsupported_present(self):
        from runtime.claim_trust_index import score_readiness_trust
        verification_data = {
            "readiness_results": [
                {"verdict": "VERIFIED"},
                {"verdict": "UNSUPPORTED"},
                {"verdict": "VERIFIED"},
                {"verdict": "VERIFIED"},
            ]
        }
        result = score_readiness_trust(verification_data)
        self.assertEqual(result["claim_group"], "readiness")
        # 3 VERIFIED (1.0 each) + 1 UNSUPPORTED (0.2) = 3.2 / 4 = 0.8 -> TRUSTED_WITH_GAPS
        self.assertGreater(result["trust_score"], 0.70)
        self.assertIn("trust_class", result)

    def test_score_posture_trust_returns_caution_on_inconsistent_claim(self):
        from runtime.claim_trust_index import score_posture_trust
        verification_data = {
            "posture_results": [
                {"verdict": "INCONSISTENT"},
                {"verdict": "VERIFIED"},
            ]
        }
        result = score_posture_trust(verification_data)
        self.assertEqual(result["claim_group"], "posture")
        # 1 VERIFIED (1.0) + 1 INCONSISTENT (0.0) = 0.5 -> CAUTION
        self.assertAlmostEqual(result["trust_score"], 0.5)
        self.assertEqual(result["trust_class"], "CAUTION")

    def test_derive_overall_trust_index_contains_required_fields(self):
        from runtime.claim_trust_index import derive_overall_trust_index
        identity_trust  = {"trust_score": 0.9, "trust_class": "HIGH_TRUST"}
        readiness_trust = {"trust_score": 0.7, "trust_class": "TRUSTED_WITH_GAPS"}
        posture_trust   = {"trust_score": 0.6, "trust_class": "CAUTION"}
        result = derive_overall_trust_index(identity_trust, readiness_trust, posture_trust)
        self.assertIn("overall_trust_score", result)
        self.assertIn("overall_trust_class", result)
        self.assertIn("claim_groups", result)
        self.assertIn("group_scores", result)
        self.assertIn("identity",  result["claim_groups"])
        self.assertIn("readiness", result["claim_groups"])
        self.assertIn("posture",   result["claim_groups"])

    def test_summarize_trust_gaps_contains_required_fields(self):
        from runtime.claim_trust_index import summarize_trust_gaps
        verification_data = {
            "all_results": [
                {"verdict": "INCONSISTENT", "claim_key": "operating_mode",
                 "claimed_value": "ACTIVE", "observed_value": "PAUSED"},
            ]
        }
        gaps = summarize_trust_gaps(verification_data, {}, {})
        self.assertIsInstance(gaps, list)
        self.assertGreater(len(gaps), 0)
        g = gaps[0]
        self.assertIn("gap_id",      g)
        self.assertIn("gap_type",    g)
        self.assertIn("severity",    g)
        self.assertIn("summary",     g)
        self.assertIn("evidence_refs", g)

    def test_store_claim_trust_writes_outputs(self):
        from runtime.claim_trust_index import store_claim_trust
        import uuid, time
        with tempfile.TemporaryDirectory() as tmp:
            rt = _make_runtime(tmp)
            report = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "run_id": str(uuid.uuid4()),
                "identity_trust":  {"trust_score": 1.0, "trust_class": "HIGH_TRUST"},
                "readiness_trust": {"trust_score": 1.0, "trust_class": "HIGH_TRUST"},
                "posture_trust":   {"trust_score": 1.0, "trust_class": "HIGH_TRUST"},
                "overall": {
                    "overall_trust_score": 1.0,
                    "overall_trust_class": "HIGH_TRUST",
                    "claim_groups": {"identity": "HIGH_TRUST", "readiness": "HIGH_TRUST", "posture": "HIGH_TRUST"},
                    "group_scores": {"identity": 1.0, "readiness": 1.0, "posture": 1.0},
                },
                "trust_gaps":    [],
                "caution_notes": [],
                "evidence_refs": [],
            }
            store_claim_trust(report, rt)
            state_dir = Path(rt) / "state"
            self.assertTrue((state_dir / "runtime_claim_trust_log.jsonl").exists())
            self.assertTrue((state_dir / "runtime_claim_trust_latest.json").exists())
            self.assertTrue((state_dir / "runtime_claim_trust_index.json").exists())


# ---------------------------------------------------------------------------
# Suite 3: Integration tests
# ---------------------------------------------------------------------------

class TestClaimTrustIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        state_dir = Path(self.rt) / "state"
        _make_verification_latest(state_dir, all_verified=True)
        _make_self_awareness_latest(state_dir)
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_claim_trust_index_generates_outputs(self):
        from runtime.claim_trust_index import run_claim_trust_index
        result = run_claim_trust_index(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("overall_trust_score", result)
        self.assertIn("overall_trust_class", result)
        state_dir = Path(self.rt) / "state"
        self.assertTrue((state_dir / "runtime_claim_trust_latest.json").exists())
        self.assertTrue((state_dir / "runtime_claim_trust_index.json").exists())
        self.assertTrue((state_dir / "runtime_claim_trust_log.jsonl").exists())

    def test_api_claim_trust_latest_returns_json(self):
        from runtime.claim_trust_index import run_claim_trust_index
        run_claim_trust_index(self.rt)
        import asyncio
        from interface.operator.api_claim_trust import claim_trust_latest
        result = asyncio.run(claim_trust_latest())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("latest", result)

    def test_api_claim_trust_index_returns_json(self):
        from runtime.claim_trust_index import run_claim_trust_index
        run_claim_trust_index(self.rt)
        import asyncio
        from interface.operator.api_claim_trust import claim_trust_index
        result = asyncio.run(claim_trust_index())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("overall_trust_score", result)

    def test_api_claim_trust_gaps_returns_json(self):
        from runtime.claim_trust_index import run_claim_trust_index
        run_claim_trust_index(self.rt)
        import asyncio
        from interface.operator.api_claim_trust import claim_trust_gaps
        result = asyncio.run(claim_trust_gaps())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("trust_gaps", result)
        self.assertIn("gap_count", result)

    def test_api_claim_trust_run_generates_outputs(self):
        """Integration: run endpoint generates all three output files."""
        from runtime.claim_trust_index import run_claim_trust_index
        result = run_claim_trust_index(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        state_dir = Path(self.rt) / "state"
        for fname in [
            "runtime_claim_trust_latest.json",
            "runtime_claim_trust_index.json",
            "runtime_claim_trust_log.jsonl",
        ]:
            self.assertTrue((state_dir / fname).exists(), msg=f"missing: {fname}")


# ---------------------------------------------------------------------------
# Suite 4: Safety / advisory-only invariant tests
# ---------------------------------------------------------------------------

class TestClaimTrustSafety(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        state_dir = Path(self.rt) / "state"
        _make_verification_latest(state_dir, all_verified=False)
        _make_self_awareness_latest(state_dir)
        # Simulate governance and campaign state files
        _write_json(state_dir / "decision_queue_governance_latest.json",
                    {"open_count": 2, "entries": []})
        _write_json(state_dir / "repair_campaign_latest.json",
                    {"campaign_id": "camp-001", "status": "OPEN"})
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _snap(self) -> dict:
        """Snapshot mtime of governance / campaign state files."""
        state_dir = Path(self.rt) / "state"
        snap = {}
        for fname in [
            "decision_queue_governance_latest.json",
            "repair_campaign_latest.json",
        ]:
            p = state_dir / fname
            snap[fname] = p.stat().st_mtime if p.exists() else None
        return snap

    def test_claim_trust_index_does_not_mutate_governance_state(self):
        from runtime.claim_trust_index import run_claim_trust_index
        before = self._snap()
        run_claim_trust_index(self.rt)
        after = self._snap()
        self.assertEqual(
            before["decision_queue_governance_latest.json"],
            after["decision_queue_governance_latest.json"],
            "AG-49 must not modify governance state",
        )

    def test_claim_trust_index_does_not_mutate_campaign_state(self):
        from runtime.claim_trust_index import run_claim_trust_index
        before = self._snap()
        run_claim_trust_index(self.rt)
        after = self._snap()
        self.assertEqual(
            before["repair_campaign_latest.json"],
            after["repair_campaign_latest.json"],
            "AG-49 must not modify campaign state",
        )

    def test_claim_trust_index_does_not_execute_repairs(self):
        from runtime.claim_trust_index import run_claim_trust_index
        state_dir = Path(self.rt) / "state"
        run_claim_trust_index(self.rt)
        # Must not create repair execution log
        self.assertFalse(
            (state_dir / "drift_repair_execution_log.jsonl").exists(),
            "AG-49 must not create repair execution log",
        )

    def test_claim_trust_index_is_advisory_only(self):
        """run_claim_trust_index result must contain only advisory fields."""
        from runtime.claim_trust_index import run_claim_trust_index
        result = run_claim_trust_index(self.rt)
        # Must NOT contain any mutation confirmation keys
        forbidden_keys = {"repaired", "repair_applied", "governance_mutated",
                          "campaign_mutated", "correction_applied"}
        for k in forbidden_keys:
            self.assertNotIn(k, result,
                             msg=f"Advisory-only violation: result contains '{k}'")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
