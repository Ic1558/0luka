"""AG-55: Tests for Governance Alert System.

3 suites, 11 tests:
  Suite 1: Unit tests — alert detection logic
  Suite 2: Integration tests
  Suite 3: Safety / alert-only invariant tests
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
    # AG-49 claim trust (with mismatch + gap)
    _w(state_dir / "runtime_claim_trust_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "overall_trust_class": "TRUSTED_WITH_GAPS",
        "overall_trust_score": 0.75,
        "trust_gaps": [
            {"gap_type": "readiness_overclaim", "severity": "HIGH",
             "summary": "Readiness overclaimed", "evidence_refs": []}
        ],
        "mismatches": [
            {"claim_key": "model_id", "claimed_value": "v1", "observed_value": "v2"}
        ],
    })
    # AG-53 integrity results
    _w(state_dir / "runtime_operator_decision_integrity_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "broken_chain": 1,
        "valid_lifecycle": 0,
        "broken_results": [
            {"recommendation_id": "rec-001", "missing_steps": ["memory_write"]}
        ],
    })
    # AG-52 governance gate
    _w(state_dir / "runtime_governance_gate_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "gated_recommendations": [
            {"recommendation_id": "rec-001", "governance_class": "HIGH_SENSITIVITY",
             "requires_operator_review": True, "recommended_review_level": "GOVERNANCE_REVIEW"}
        ],
        "total_count": 1, "high_sensitivity": 1, "critical": 0,
    })
    # AG-54 feedback
    _w(state_dir / "runtime_recommendation_feedback_latest.json", {
        "ts": "2026-03-16T00:00:00Z",
        "recommendations_total": 1,
        "feedback_counts": {"FOLLOWED": 0, "DEFERRED": 0, "OVERRIDDEN": 1, "IGNORED": 0, "INCONCLUSIVE": 0},
        "feedback_entries": [
            {"recommendation_id": "rec-001", "feedback_class": "OVERRIDDEN",
             "summary": "Operator overrode recommendation.", "divergence_severity": "HIGH"}
        ],
        "gaps": [
            {"recommendation_id": "rec-001", "feedback_class": "OVERRIDDEN",
             "summary": "Operator overrode recommendation.", "divergence_severity": "HIGH"}
        ],
    })
    # Campaign state (mutation check)
    _w(state_dir / "repair_campaign_latest.json",
       {"campaign_id": "camp-001", "status": "OPEN"})


# ---------------------------------------------------------------------------
# Suite 1: Unit tests
# ---------------------------------------------------------------------------

class TestAlertsUnit(unittest.TestCase):

    def _trust_data(self, **kwargs):
        base = {"present": True, "trust_gaps": [], "overall_trust_class": "TRUSTED_WITH_GAPS",
                "overall_trust_score": 0.75, "mismatches": []}
        base.update(kwargs)
        return base

    def _integrity_data(self, **kwargs):
        base = {"present": True, "broken_chain": 0, "broken_results": [], "valid_lifecycle": 1}
        base.update(kwargs)
        return base

    def _gate_data(self, **kwargs):
        base = {"present": True, "gated_recommendations": [], "high_sensitivity": 0,
                "critical": 0, "total_count": 0}
        base.update(kwargs)
        return base

    def _feedback_data(self, **kwargs):
        base = {"present": True, "gaps": [], "feedback_counts": {}, "recommendations_total": 0}
        base.update(kwargs)
        return base

    def test_detect_alert_conditions_claim_mismatch(self):
        """Mismatch in trust data → CLAIM_MISMATCH_ALERT."""
        from runtime.governance_alerts import detect_alert_conditions
        trust = self._trust_data(mismatches=[
            {"claim_key": "model_id", "claimed_value": "v1", "observed_value": "v2"}
        ])
        alerts = detect_alert_conditions(
            trust, self._integrity_data(), self._gate_data(), self._feedback_data()
        )
        classes = [a["alert_class"] for a in alerts]
        self.assertIn("CLAIM_MISMATCH_ALERT", classes)

    def test_detect_alert_conditions_integrity_break(self):
        """Broken lifecycle chain → GOVERNANCE_INTEGRITY_BREAK."""
        from runtime.governance_alerts import detect_alert_conditions
        integrity = self._integrity_data(
            broken_chain=1,
            broken_results=[{"recommendation_id": "rec-001", "missing_steps": ["memory_write"]}],
        )
        alerts = detect_alert_conditions(
            self._trust_data(), integrity, self._gate_data(), self._feedback_data()
        )
        classes = [a["alert_class"] for a in alerts]
        self.assertIn("GOVERNANCE_INTEGRITY_BREAK", classes)

    def test_alert_report_contains_required_fields(self):
        """Alert report has ts, run_id, alert_count, alerts, severity_counts."""
        from runtime.governance_alerts import detect_alert_conditions
        import time, uuid
        alerts = detect_alert_conditions(
            self._trust_data(), self._integrity_data(),
            self._gate_data(high_sensitivity=1), self._feedback_data()
        )
        self.assertIsInstance(alerts, list)
        for a in alerts:
            self.assertIn("alert_class", a)
            self.assertIn("severity", a)
            self.assertIn("title", a)

    def test_store_governance_alerts_writes_outputs(self):
        """store_governance_alerts writes all three required files."""
        from runtime.governance_alerts import store_governance_alerts
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        try:
            rt = Path(tmp) / "runtime"
            (rt / "state").mkdir(parents=True)
            report = {
                "ts": "2026-03-16T00:00:00Z", "run_id": "test-run",
                "alert_count": 1, "high_alert_count": 1,
                "severity_counts": {"INFO": 0, "WARNING": 0, "HIGH": 1, "CRITICAL": 0},
                "alerts": [{"alert_class": "TRUST_GAP_ALERT", "severity": "WARNING"}],
                "high_alerts": [],
                "evidence_refs": [],
            }
            store_governance_alerts(report, str(rt))
            state_dir = rt / "state"
            self.assertTrue((state_dir / "runtime_governance_alerts_latest.json").exists())
            self.assertTrue((state_dir / "runtime_governance_alerts_index.json").exists())
            self.assertTrue((state_dir / "runtime_governance_alerts_log.jsonl").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Suite 2: Integration tests
# ---------------------------------------------------------------------------

class TestAlertsIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.rt  = _make_runtime(self.tmp)
        _seed_full_state(Path(self.rt) / "state")
        os.environ["LUKA_RUNTIME_ROOT"] = self.rt

    def tearDown(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_governance_alerts_generates_outputs(self):
        from runtime.governance_alerts import run_governance_alerts
        result = run_governance_alerts(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("alert_count", result)
        self.assertIn("severity_counts", result)
        state_dir = Path(self.rt) / "state"
        for f in [
            "runtime_governance_alerts_latest.json",
            "runtime_governance_alerts_index.json",
            "runtime_governance_alerts_log.jsonl",
        ]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")

    def test_api_governance_alerts_latest_returns_json(self):
        from runtime.governance_alerts import run_governance_alerts
        run_governance_alerts(self.rt)
        from interface.operator.api_governance_alerts import governance_alerts_latest
        result = asyncio.run(governance_alerts_latest())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("latest", result)

    def test_api_governance_alerts_index_returns_json(self):
        from runtime.governance_alerts import run_governance_alerts
        run_governance_alerts(self.rt)
        from interface.operator.api_governance_alerts import governance_alerts_index
        result = asyncio.run(governance_alerts_index())
        self.assertTrue(result.get("ok"), msg=result)
        self.assertIn("alert_count", result)

    def test_api_governance_alerts_run_generates_outputs(self):
        from runtime.governance_alerts import run_governance_alerts
        result = run_governance_alerts(self.rt)
        self.assertTrue(result.get("ok"), msg=result)
        state_dir = Path(self.rt) / "state"
        for f in [
            "runtime_governance_alerts_latest.json",
            "runtime_governance_alerts_index.json",
            "runtime_governance_alerts_log.jsonl",
        ]:
            self.assertTrue((state_dir / f).exists(), msg=f"missing: {f}")


# ---------------------------------------------------------------------------
# Suite 3: Safety / alert-only invariant tests
# ---------------------------------------------------------------------------

class TestAlertsSafety(unittest.TestCase):

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

    def test_governance_alerts_do_not_mutate_governance_state(self):
        """Governance and campaign state must not be touched."""
        from runtime.governance_alerts import run_governance_alerts
        before_gate = self._mtime("runtime_governance_gate_latest.json")
        before_camp = self._mtime("repair_campaign_latest.json")
        run_governance_alerts(self.rt)
        self.assertEqual(before_gate, self._mtime("runtime_governance_gate_latest.json"))
        self.assertEqual(before_camp, self._mtime("repair_campaign_latest.json"))

    def test_governance_alerts_do_not_execute_repairs(self):
        """No repair execution log must be created."""
        from runtime.governance_alerts import run_governance_alerts
        run_governance_alerts(self.rt)
        self.assertFalse(
            (Path(self.rt) / "state" / "drift_repair_execution_log.jsonl").exists()
        )

    def test_governance_alerts_are_alert_only(self):
        """Result must not contain any mutation confirmation keys."""
        from runtime.governance_alerts import run_governance_alerts
        result = run_governance_alerts(self.rt)
        forbidden = {"repaired", "repair_applied", "governance_mutated",
                     "campaign_mutated", "correction_applied", "decision_approved",
                     "escalated", "auto_escalated"}
        for k in forbidden:
            self.assertNotIn(k, result, msg=f"Mutation key found: '{k}'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
