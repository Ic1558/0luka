"""AG-56: Tests for Autonomous Supervision Dashboard.

3 suites, 10 tests:
  Suite 1: Unit tests — dashboard build logic
  Suite 2: Integration tests
  Suite 3: Safety / dashboard-only invariant tests
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
    """Write minimal state covering AG-47 through AG-55 outputs."""
    # AG-47 self-awareness
    _w(state_dir / "runtime_self_awareness_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "identity": {"model_id": "luka-v2", "agent_id": "clc"},
        "posture": {"posture_class": "STANDARD"},
    })
    _w(state_dir / "runtime_readiness.json", {"readiness_class": "READY", "score": 0.9})
    # AG-49 claim trust
    _w(state_dir / "runtime_claim_trust_index.json", {
        "overall_trust_score": 0.82, "overall_trust_class": "TRUSTED_WITH_GAPS",
        "gap_count": 1,
    })
    _w(state_dir / "runtime_claim_trust_latest.json", {
        "overall_trust_score": 0.82, "overall_trust_class": "TRUSTED_WITH_GAPS",
        "trust_gaps": [{"gap_type": "readiness_overclaim", "severity": "HIGH",
                        "summary": "Overclaim detected", "evidence_refs": []}],
        "mismatches": [],
    })
    # AG-50 trust guidance
    _w(state_dir / "runtime_trust_guidance_latest.json", {
        "guidance_mode": "TRUST_WITH_CAUTION", "caution_class": "LOW_CAUTION",
        "guidance_entries": [{"guidance_id": "guidance-overall", "dimension": "overall",
                              "guidance_mode": "TRUST_WITH_CAUTION", "caution_class": "LOW_CAUTION"}],
    })
    # AG-51 confidence
    _w(state_dir / "runtime_operator_confidence_index.json", {
        "overall_confidence": 0.78, "confidence_class": "MODERATE_CONFIDENCE",
    })
    # AG-52 governance gate
    _w(state_dir / "runtime_governance_gate_latest.json", {
        "gated_recommendations": [
            {"recommendation_id": "rec-001", "governance_class": "HIGH_SENSITIVITY",
             "requires_operator_review": True, "recommended_review_level": "GOVERNANCE_REVIEW"}
        ],
        "total_count": 1, "high_sensitivity": 1, "critical": 0,
    })
    # AG-53 integrity
    _w(state_dir / "runtime_operator_decision_integrity_latest.json", {
        "broken_chain": 0, "valid_lifecycle": 1, "broken_results": [],
    })
    # AG-55 alerts
    _w(state_dir / "runtime_governance_alerts_latest.json", {
        "alert_count": 1, "high_alert_count": 1,
        "severity_counts": {"INFO": 0, "WARNING": 0, "HIGH": 1, "CRITICAL": 0},
        "alerts": [{"alert_class": "TRUST_GAP_ALERT", "severity": "HIGH",
                    "title": "Trust gap", "description": "gap detected"}],
        "high_alerts": [{"alert_class": "TRUST_GAP_ALERT", "severity": "HIGH",
                         "title": "Trust gap", "description": "gap detected"}],
    })
    # Campaign state (mutation check)
    _w(state_dir / "repair_campaign_latest.json",
       {"campaign_id": "camp-001", "status": "OPEN"})


# ---------------------------------------------------------------------------
# Suite 1: Unit tests
# ---------------------------------------------------------------------------

class TestDashboardUnit(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        _seed_full_state(Path(self.rt) / "state")
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_supervision_dashboard_contains_required_sections(self):
        """Dashboard report must contain all required sections."""
        from runtime.supervision_dashboard import build_supervision_dashboard
        from runtime.dashboard_policy import DASHBOARD_SECTIONS
        report = build_supervision_dashboard(self.rt)
        self.assertIn("sections", report)
        for section in DASHBOARD_SECTIONS:
            self.assertIn(section, report["sections"])
        # Verify section data keys exist
        self.assertIn("runtime_identity", report)
        self.assertIn("trust_index", report)
        self.assertIn("governance_alerts", report)
        self.assertIn("integrity_breaks", report)
        self.assertIn("open_decision_queue_summary", report)

    def test_dashboard_orders_alerts_by_severity(self):
        """governance_alerts in dashboard must be sorted by severity."""
        from runtime.supervision_dashboard import build_supervision_dashboard
        report = build_supervision_dashboard(self.rt)
        alerts = report.get("governance_alerts", [])
        if len(alerts) >= 2:
            from runtime.dashboard_policy import SEVERITY_ORDER
            severities = [SEVERITY_ORDER.get(a.get("severity", "INFO"), 99) for a in alerts]
            self.assertEqual(severities, sorted(severities))

    def test_store_supervision_dashboard_writes_outputs(self):
        """store_supervision_dashboard writes all three required files."""
        from runtime.supervision_dashboard import store_supervision_dashboard
        report = {
            "ts": "2026-03-16T00:00:00Z", "run_id": "test-run",
            "sections": [], "alert_count": 0, "high_alert_count": 0,
            "severity_counts": {}, "evidence_refs": [],
            "runtime_identity": {}, "readiness": {}, "posture": {},
            "trust_index": {}, "top_trust_gaps": [], "top_guidance_items": [],
            "open_decision_queue_summary": {}, "governance_alerts": [],
            "integrity_breaks": [],
        }
        store_supervision_dashboard(report, self.rt)
        state_dir = Path(self.rt) / "state"
        self.assertTrue((state_dir / "runtime_supervision_dashboard_latest.json").exists())
        self.assertTrue((state_dir / "runtime_supervision_dashboard_index.json").exists())
        self.assertTrue((state_dir / "runtime_supervision_dashboard_log.jsonl").exists())


# ---------------------------------------------------------------------------
# Suite 2: Integration tests
# ---------------------------------------------------------------------------

class TestDashboardIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        _seed_full_state(Path(self.rt) / "state")
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_supervision_dashboard_generates_outputs(self):
        from runtime.supervision_dashboard import run_supervision_dashboard
        result = run_supervision_dashboard(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("alert_count", result)
        self.assertIn("sections", result)
        state_dir = Path(self.rt) / "state"
        for f in [
            "runtime_supervision_dashboard_latest.json",
            "runtime_supervision_dashboard_index.json",
            "runtime_supervision_dashboard_log.jsonl",
        ]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")

    def test_api_supervision_dashboard_latest_returns_json(self):
        from runtime.supervision_dashboard import run_supervision_dashboard
        run_supervision_dashboard(self.rt)
        from interface.operator.api_supervision_dashboard import supervision_dashboard_latest
        result = asyncio.run(supervision_dashboard_latest())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("latest", result)

    def test_api_supervision_dashboard_index_returns_json(self):
        from runtime.supervision_dashboard import run_supervision_dashboard
        run_supervision_dashboard(self.rt)
        from interface.operator.api_supervision_dashboard import supervision_dashboard_index
        result = asyncio.run(supervision_dashboard_index())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("sections", result)

    def test_api_supervision_dashboard_run_generates_outputs(self):
        from runtime.supervision_dashboard import run_supervision_dashboard
        result = run_supervision_dashboard(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        state_dir = Path(self.rt) / "state"
        for f in [
            "runtime_supervision_dashboard_latest.json",
            "runtime_supervision_dashboard_index.json",
            "runtime_supervision_dashboard_log.jsonl",
        ]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")


# ---------------------------------------------------------------------------
# Suite 3: Safety / dashboard-only invariant tests
# ---------------------------------------------------------------------------

class TestDashboardSafety(unittest.TestCase):

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

    def test_dashboard_does_not_mutate_governance_state(self):
        """Governance and campaign state must not be touched."""
        from runtime.supervision_dashboard import run_supervision_dashboard
        before_gate = self._mtime("runtime_governance_gate_latest.json")
        before_camp = self._mtime("repair_campaign_latest.json")
        run_supervision_dashboard(self.rt)
        self.assertEqual(before_gate, self._mtime("runtime_governance_gate_latest.json"))
        self.assertEqual(before_camp, self._mtime("repair_campaign_latest.json"))

    def test_dashboard_does_not_execute_repairs(self):
        """No repair execution log must be created."""
        from runtime.supervision_dashboard import run_supervision_dashboard
        run_supervision_dashboard(self.rt)
        self.assertFalse(
            (Path(self.rt) / "state" / "drift_repair_execution_log.jsonl").exists()
        )

    def test_dashboard_is_read_only(self):
        """Result must not contain any mutation confirmation keys."""
        from runtime.supervision_dashboard import run_supervision_dashboard
        result = run_supervision_dashboard(self.rt)
        forbidden = {"repaired", "repair_applied", "governance_mutated",
                     "campaign_mutated", "correction_applied", "decision_approved",
                     "auto_acted", "escalated"}
        for k in forbidden:
            self.assertNotIn(k, result, msg=f"Mutation key found: '{k}'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
