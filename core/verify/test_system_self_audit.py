"""AG-57: Tests for System Self-Audit Layer.

3 suites, 11 tests:
  Suite 1: Unit tests — stack coherence verification
  Suite 2: Integration tests
  Suite 3: Safety / audit-only invariant tests
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
    """Write all required AG-47 through AG-56 artifacts."""
    _w(state_dir / "runtime_self_awareness_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "identity": {"model_id": "luka-v2"}, "posture": {"posture_class": "STANDARD"},
    })
    _w(state_dir / "runtime_readiness.json", {"readiness_class": "READY"})
    _w(state_dir / "runtime_claim_trust_index.json", {
        "overall_trust_score": 0.82, "overall_trust_class": "TRUSTED_WITH_GAPS", "gap_count": 1,
    })
    _w(state_dir / "runtime_claim_trust_latest.json", {
        "overall_trust_score": 0.82, "overall_trust_class": "TRUSTED_WITH_GAPS",
        "trust_gaps": [], "mismatches": [],
    })
    _w(state_dir / "runtime_trust_guidance_latest.json", {
        "guidance_mode": "TRUST_WITH_CAUTION", "guidance_entries": [],
    })
    _w(state_dir / "runtime_operator_confidence_latest.json", {
        "overall_confidence": 0.78, "confidence_class": "MODERATE_CONFIDENCE",
    })
    _w(state_dir / "runtime_operator_confidence_index.json", {
        "overall_confidence": 0.78, "confidence_class": "MODERATE_CONFIDENCE",
    })
    _w(state_dir / "runtime_governance_gate_latest.json", {
        "gated_recommendations": [], "total_count": 0, "high_sensitivity": 0, "critical": 0,
    })
    _w(state_dir / "runtime_operator_decision_integrity_latest.json", {
        "broken_chain": 0, "valid_lifecycle": 0, "broken_results": [],
    })
    _w(state_dir / "runtime_recommendation_feedback_latest.json", {
        "recommendations_total": 0, "feedback_counts": {}, "feedback_entries": [], "gaps": [],
    })
    _w(state_dir / "runtime_governance_alerts_latest.json", {
        "alert_count": 0, "high_alert_count": 0, "severity_counts": {},
        "alerts": [], "high_alerts": [],
    })
    _w(state_dir / "runtime_supervision_dashboard_latest.json", {
        "alert_count": 0, "high_alert_count": 0, "severity_counts": {},
        "sections": [], "trust_index": {"overall_trust_score": 0.82},
        "governance_alerts": [], "integrity_breaks": [],
        "open_decision_queue_summary": {}, "top_trust_gaps": [],
        "top_guidance_items": [], "runtime_identity": {}, "readiness": {}, "posture": {},
    })
    # Campaign state (mutation check)
    _w(state_dir / "repair_campaign_latest.json",
       {"campaign_id": "camp-001", "status": "OPEN"})


# ---------------------------------------------------------------------------
# Suite 1: Unit tests
# ---------------------------------------------------------------------------

class TestSelfAuditUnit(unittest.TestCase):

    def _loader_args(self, overrides: dict | None = None) -> tuple:
        base = {
            "sa":        {"present": True, "data": {}},
            "trust":     {"present": True, "data": {}},
            "guidance":  {"present": True, "data": {}},
            "gate":      {"present": True, "data": {}},
            "integrity": {"present": True, "data": {}},
            "alert":     {"present": True, "data": {"alert_count": 0}},
            "dashboard": {"present": True, "data": {"trust_index": {}, "alert_count": 0}},
        }
        if overrides:
            base.update(overrides)
        return (
            base["sa"], base["trust"], base["guidance"], base["gate"],
            base["integrity"], base["alert"], base["dashboard"],
        )

    def test_verify_stack_coherence_returns_coherent_when_all_artifacts_present(self):
        """All artifacts present → STACK_COHERENT."""
        from runtime.system_self_audit import verify_stack_coherence
        args = self._loader_args()
        result = verify_stack_coherence(*args)
        self.assertEqual(result["verdict"], "STACK_COHERENT")
        self.assertEqual(result["missing_count"], 0)

    def test_verify_stack_coherence_returns_gaps_when_missing_outputs(self):
        """Missing self_awareness → verdict not STACK_COHERENT, missing list populated."""
        from runtime.system_self_audit import verify_stack_coherence
        args = self._loader_args({"sa": {"present": False, "data": {}}})
        result = verify_stack_coherence(*args)
        self.assertNotEqual(result["verdict"], "STACK_COHERENT")
        self.assertIn("self_awareness_present", result["missing"])

    def test_self_audit_report_contains_required_sections(self):
        """build_system_self_audit_report must include verdict, coherence, artifact_audit."""
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        try:
            rt = Path(tmp) / "runtime"
            (rt / "state").mkdir(parents=True)
            _seed_full_state(rt / "state")
            os.environ["LUKA_RUNTIME_ROOT"] = str(rt)
            from runtime.system_self_audit import build_system_self_audit_report
            report = build_system_self_audit_report(str(rt))
            self.assertIn("verdict", report)
            self.assertIn("coherence", report)
            self.assertIn("artifact_audit", report)
            self.assertIn("missing_count", report)
            self.assertIn("gaps", report)
            from runtime.system_self_audit_policy import AUDIT_VERDICTS
            self.assertIn(report["verdict"], AUDIT_VERDICTS)
        finally:
            os.environ.pop("LUKA_RUNTIME_ROOT", None)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_store_system_self_audit_writes_outputs(self):
        """store_system_self_audit writes all three required files."""
        from runtime.system_self_audit import store_system_self_audit
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        try:
            rt = Path(tmp) / "runtime"
            (rt / "state").mkdir(parents=True)
            report = {
                "ts": "2026-03-16T00:00:00Z", "run_id": "test-run",
                "verdict": "STACK_COHERENT",
                "coherence": {"checks": {}, "missing": [], "incoherent": [],
                              "missing_count": 0, "incoherent_count": 0, "verdict": "STACK_COHERENT"},
                "artifact_audit": {"all_present": True, "layers": {}},
                "missing_count": 0, "incoherent_count": 0, "gaps": [], "evidence_refs": [],
            }
            store_system_self_audit(report, str(rt))
            state_dir = rt / "state"
            self.assertTrue((state_dir / "runtime_system_self_audit_latest.json").exists())
            self.assertTrue((state_dir / "runtime_system_self_audit_index.json").exists())
            self.assertTrue((state_dir / "runtime_system_self_audit_log.jsonl").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Suite 2: Integration tests
# ---------------------------------------------------------------------------

class TestSelfAuditIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        _seed_full_state(Path(self.rt) / "state")
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_system_self_audit_generates_outputs(self):
        from runtime.system_self_audit import run_system_self_audit
        result = run_system_self_audit(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("verdict", result)
        self.assertIn("missing_count", result)
        state_dir = Path(self.rt) / "state"
        for f in [
            "runtime_system_self_audit_latest.json",
            "runtime_system_self_audit_index.json",
            "runtime_system_self_audit_log.jsonl",
        ]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")

    def test_api_system_self_audit_latest_returns_json(self):
        from runtime.system_self_audit import run_system_self_audit
        run_system_self_audit(self.rt)
        from interface.operator.api_system_self_audit import system_self_audit_latest
        result = asyncio.run(system_self_audit_latest())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("latest", result)

    def test_api_system_self_audit_index_returns_json(self):
        from runtime.system_self_audit import run_system_self_audit
        run_system_self_audit(self.rt)
        from interface.operator.api_system_self_audit import system_self_audit_index
        result = asyncio.run(system_self_audit_index())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("verdict", result)

    def test_api_system_self_audit_run_generates_outputs(self):
        from runtime.system_self_audit import run_system_self_audit
        result = run_system_self_audit(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        state_dir = Path(self.rt) / "state"
        for f in [
            "runtime_system_self_audit_latest.json",
            "runtime_system_self_audit_index.json",
            "runtime_system_self_audit_log.jsonl",
        ]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")


# ---------------------------------------------------------------------------
# Suite 3: Safety / audit-only invariant tests
# ---------------------------------------------------------------------------

class TestSelfAuditSafety(unittest.TestCase):

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

    def test_system_self_audit_does_not_mutate_governance_state(self):
        """Governance and campaign state must not be touched."""
        from runtime.system_self_audit import run_system_self_audit
        before_gate = self._mtime("runtime_governance_gate_latest.json")
        before_camp = self._mtime("repair_campaign_latest.json")
        run_system_self_audit(self.rt)
        self.assertEqual(before_gate, self._mtime("runtime_governance_gate_latest.json"))
        self.assertEqual(before_camp, self._mtime("repair_campaign_latest.json"))

    def test_system_self_audit_does_not_execute_repairs(self):
        """No repair execution log must be created."""
        from runtime.system_self_audit import run_system_self_audit
        run_system_self_audit(self.rt)
        self.assertFalse(
            (Path(self.rt) / "state" / "drift_repair_execution_log.jsonl").exists()
        )

    def test_system_self_audit_is_audit_only(self):
        """Result must not contain any mutation confirmation keys."""
        from runtime.system_self_audit import run_system_self_audit
        result = run_system_self_audit(self.rt)
        forbidden = {"repaired", "repair_applied", "governance_mutated",
                     "campaign_mutated", "correction_applied", "decision_approved",
                     "auto_corrected", "enforced"}
        for k in forbidden:
            self.assertNotIn(k, result, msg=f"Mutation key found: '{k}'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
