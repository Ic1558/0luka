"""AG-37: Drift Intelligence Layer — test suite.

Tests:
  A. Drift Pattern Registry
  B. Intelligence Engine — Unit
  C. Intelligence Engine — Integration
  D. Safety Invariants
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tmpdir() -> str:
    td = tempfile.mkdtemp()
    os.environ["LUKA_RUNTIME_ROOT"] = td
    (Path(td) / "state").mkdir(parents=True, exist_ok=True)
    return td


def _write_jsonl(td: str, filename: str, records: list[dict]) -> None:
    path = Path(td) / "state" / filename
    with path.open("a") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _mock_request(body: dict[str, Any]) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


def _sample_findings(n: int = 4, drift_class: str = "naming_drift_only") -> list[dict]:
    return [
        {"id": f"f{i}", "finding_id": f"f{i}", "drift_class": drift_class,
         "component": f"core.module_{i}", "status": "OPEN"}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Suite A: Drift Pattern Registry
# ---------------------------------------------------------------------------

class TestDriftPatternRegistry:

    def test_all_eight_pattern_classes_registered(self):
        from core.audit.drift_pattern_registry import PATTERN_CLASSES
        required = {
            "recurring_naming_drift",
            "recurring_route_surface_drift",
            "recurring_operator_gate_regression",
            "recurring_state_file_absence",
            "recurring_legacy_overlap",
            "recurring_failed_repair_cycle",
            "recurring_baseline_mismatch",
            "recurring_reconciliation_failure",
        }
        assert required.issubset(set(PATTERN_CLASSES.keys()))

    def test_is_valid_pattern_class(self):
        from core.audit.drift_pattern_registry import is_valid_pattern_class
        assert is_valid_pattern_class("recurring_naming_drift") is True
        assert is_valid_pattern_class("nonexistent_class") is False

    def test_default_pattern_severity(self):
        from core.audit.drift_pattern_registry import default_pattern_severity
        assert default_pattern_severity("recurring_operator_gate_regression") == "CRITICAL"
        assert default_pattern_severity("recurring_naming_drift") == "LOW"
        assert default_pattern_severity("unknown") == "MEDIUM"

    def test_classify_drift_to_pattern(self):
        from core.audit.drift_pattern_registry import classify_drift_to_pattern
        assert classify_drift_to_pattern("naming_drift_only") == "recurring_naming_drift"
        assert classify_drift_to_pattern("operator_gate_missing") == "recurring_operator_gate_regression"
        assert classify_drift_to_pattern("legacy_component_still_active") == "recurring_legacy_overlap"
        assert classify_drift_to_pattern("unknown_drift") is None

    def test_all_pattern_class_names_returns_all(self):
        from core.audit.drift_pattern_registry import all_pattern_class_names
        names = all_pattern_class_names()
        assert len(names) == 8

    def test_severity_value_ordering(self):
        from core.audit.drift_pattern_registry import severity_value
        assert severity_value("CRITICAL") > severity_value("HIGH")
        assert severity_value("HIGH") > severity_value("MEDIUM")
        assert severity_value("MEDIUM") > severity_value("LOW")


# ---------------------------------------------------------------------------
# Suite B: Intelligence Engine Unit Tests
# ---------------------------------------------------------------------------

class TestIntelligenceEngineUnit:

    def test_detect_drift_patterns_groups_recurring_findings(self):
        from core.audit.drift_intelligence import detect_drift_patterns
        findings = _sample_findings(4, "naming_drift_only")
        patterns = detect_drift_patterns(findings)
        assert len(patterns) >= 1
        classes = {p["pattern_class"] for p in patterns}
        assert "recurring_naming_drift" in classes

    def test_detect_drift_patterns_excludes_single_occurrence(self):
        from core.audit.drift_intelligence import detect_drift_patterns
        findings = [{"id": "f1", "drift_class": "naming_drift_only", "component": "core.a"}]
        patterns = detect_drift_patterns(findings)
        assert len(patterns) == 0

    def test_detect_drift_patterns_includes_reconciliation_failures(self):
        from core.audit.drift_intelligence import detect_drift_patterns
        reconciliations = [
            {"reconciliation_id": "r1", "finding_id": "f1", "verification_status": "FAILED"},
            {"reconciliation_id": "r2", "finding_id": "f2", "verification_status": "INCONCLUSIVE"},
        ]
        patterns = detect_drift_patterns([], reconciliations, [])
        classes = {p["pattern_class"] for p in patterns}
        assert "recurring_reconciliation_failure" in classes

    def test_detect_drift_patterns_includes_repair_failures(self):
        from core.audit.drift_intelligence import detect_drift_patterns
        repairs = [
            {"execution_id": "e1", "finding_id": "f1", "status": "FAILED"},
            {"execution_id": "e2", "finding_id": "f2", "status": "FAILED"},
        ]
        patterns = detect_drift_patterns([], [], repairs)
        classes = {p["pattern_class"] for p in patterns}
        assert "recurring_failed_repair_cycle" in classes

    def test_score_runtime_stability_returns_deterministic_score(self):
        from core.audit.drift_intelligence import score_runtime_stability
        findings = [
            {"drift_class": "naming_drift_only", "gov_status": "OPEN"},
            {"drift_class": "naming_drift_only", "gov_status": "ACCEPTED"},
        ]
        patterns = []
        score_result = score_runtime_stability(findings, patterns, [], [])
        assert "score" in score_result
        assert "classification" in score_result
        assert "factors" in score_result
        assert isinstance(score_result["score"], int)
        assert 0 <= score_result["score"] <= 100

    def test_score_stable_when_no_issues(self):
        from core.audit.drift_intelligence import score_runtime_stability
        result = score_runtime_stability([], [], [], [])
        assert result["score"] == 100
        assert result["classification"] == "STABLE"

    def test_score_penalized_for_escalated_findings(self):
        from core.audit.drift_intelligence import score_runtime_stability
        findings = [{"gov_status": "ESCALATED"}, {"gov_status": "ESCALATED"}]
        result = score_runtime_stability(findings, [], [], [])
        assert result["score"] < 100
        assert result["factors"]["escalated_findings"] == 2

    def test_score_governance_risk_for_violations(self):
        from core.audit.drift_intelligence import score_runtime_stability
        # Many violations → should push score toward GOVERNANCE_RISK
        findings = [{"drift_class": "operator_gate_missing", "gov_status": "OPEN"}] * 10
        patterns = [{"pattern_class": "recurring_operator_gate_regression", "severity": "CRITICAL", "instance_count": 10}] * 4
        result = score_runtime_stability(findings, patterns, [], [])
        assert result["score"] < 60

    def test_identify_drift_hotspots_ranks_components(self):
        from core.audit.drift_intelligence import identify_drift_hotspots
        findings = (
            [{"component": "hot_component.py"}] * 5 +
            [{"component": "warm_component.py"}] * 2 +
            [{"component": "cold_component.py"}] * 1
        )
        hotspots = identify_drift_hotspots(findings)
        assert hotspots[0]["component"] == "hot_component.py"
        assert hotspots[0]["drift_count"] == 5
        assert hotspots[0]["risk"] == "HIGH"

    def test_identify_drift_hotspots_empty_returns_empty(self):
        from core.audit.drift_intelligence import identify_drift_hotspots
        assert identify_drift_hotspots([]) == []

    def test_generate_drift_intelligence_report_contains_required_sections(self):
        td = _make_tmpdir()
        _write_jsonl(td, "drift_findings.jsonl", _sample_findings(3, "naming_drift_only"))
        from core.audit.drift_intelligence import generate_drift_intelligence_report
        report = generate_drift_intelligence_report(td)
        required_keys = ("ts", "report_id", "total_findings_trend", "recurring_patterns",
                         "hotspot_components", "repair_summary", "governance_risk_summary",
                         "stability_score", "recommendations")
        for k in required_keys:
            assert k in report, f"missing section: {k}"

    def test_store_drift_intelligence_writes_latest_and_log(self):
        td = _make_tmpdir()
        from core.audit.drift_intelligence import store_drift_intelligence
        report = {
            "report_id": "intel-test",
            "ts": "2026-03-16T00:00:00Z",
            "recurring_patterns": [],
            "stability_score": {"score": 100, "classification": "STABLE"},
        }
        store_drift_intelligence(report, td)
        state = Path(td) / "state"
        assert (state / "drift_intelligence_log.jsonl").exists()
        assert (state / "drift_intelligence_latest.json").exists()
        assert (state / "drift_pattern_registry.json").exists()
        assert (state / "runtime_stability_score.json").exists()


# ---------------------------------------------------------------------------
# Suite C: Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_run_drift_intelligence_produces_pattern_registry(self):
        td = _make_tmpdir()
        _write_jsonl(td, "drift_findings.jsonl", _sample_findings(4, "naming_drift_only"))
        from core.audit.drift_intelligence import run_drift_intelligence
        result = run_drift_intelligence(td)
        assert result["ok"] is True
        assert (Path(td) / "state" / "drift_pattern_registry.json").exists()

    def test_run_drift_intelligence_produces_stability_score(self):
        td = _make_tmpdir()
        from core.audit.drift_intelligence import run_drift_intelligence
        result = run_drift_intelligence(td)
        assert "stability_score" in result
        assert "classification" in result

    def test_run_drift_intelligence_empty_history_is_deterministic(self):
        td = _make_tmpdir()
        from core.audit.drift_intelligence import run_drift_intelligence
        result = run_drift_intelligence(td)
        assert result["ok"] is True
        assert result["stability_score"] == 100
        assert result["classification"] == "STABLE"
        assert result["patterns_detected"] == 0

    def test_api_drift_intelligence_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_drift_intelligence import drift_intelligence_latest
        result = asyncio.run(drift_intelligence_latest())
        assert result["ok"] is True
        assert "report" in result

    def test_api_drift_intelligence_patterns_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_drift_intelligence import drift_intelligence_patterns
        result = asyncio.run(drift_intelligence_patterns())
        assert result["ok"] is True
        assert "patterns" in result

    def test_api_drift_intelligence_hotspots_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_drift_intelligence import drift_intelligence_hotspots
        result = asyncio.run(drift_intelligence_hotspots())
        assert result["ok"] is True
        assert "hotspots" in result

    def test_api_drift_intelligence_stability_returns_score(self):
        td = _make_tmpdir()
        _write_jsonl(td, "drift_findings.jsonl", [])
        from core.audit.drift_intelligence import run_drift_intelligence
        run_drift_intelligence(td)
        from interface.operator.api_drift_intelligence import drift_intelligence_stability
        result = asyncio.run(drift_intelligence_stability())
        assert result["ok"] is True
        assert "stability" in result

    def test_api_drift_intelligence_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_drift_intelligence import drift_intelligence_run
        req = _mock_request({})
        resp = asyncio.run(drift_intelligence_run(req))
        assert resp.status_code == 403

    def test_api_drift_intelligence_run_generates_outputs(self):
        td = _make_tmpdir()
        _write_jsonl(td, "drift_findings.jsonl", _sample_findings(3))
        from interface.operator.api_drift_intelligence import drift_intelligence_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(drift_intelligence_run(req))
        data = json.loads(resp.body)
        assert data["ok"] is True
        assert "stability_score" in data
        assert "classification" in data


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_drift_intelligence_does_not_modify_governance_state(self):
        td = _make_tmpdir()
        state = Path(td) / "state"
        status_path = state / "drift_finding_status.json"
        status_path.write_text(json.dumps({"f1": {"status": "ESCALATED"}}))
        mtime_before = status_path.stat().st_mtime
        from core.audit.drift_intelligence import run_drift_intelligence
        run_drift_intelligence(td)
        mtime_after = status_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_drift_intelligence_does_not_modify_baseline(self):
        td = _make_tmpdir()
        baseline_path = Path(__file__).parent.parent / "audit" / "audit_baseline.py"
        mtime_before = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        from core.audit.drift_intelligence import run_drift_intelligence
        run_drift_intelligence(td)
        mtime_after = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        assert mtime_before == mtime_after

    def test_drift_intelligence_does_not_execute_repairs(self):
        td = _make_tmpdir()
        from core.audit.drift_intelligence import run_drift_intelligence
        result = run_drift_intelligence(td)
        # Only allowed output files should exist
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        forbidden = {"drift_repair_execution_log.jsonl", "drift_finding_status.json"}
        assert not (written & forbidden), f"forbidden files written: {written & forbidden}"

    def test_drift_intelligence_is_analysis_only(self):
        td = _make_tmpdir()
        _write_jsonl(td, "drift_findings.jsonl", _sample_findings(5, "operator_gate_missing"))
        from core.audit.drift_intelligence import run_drift_intelligence
        result = run_drift_intelligence(td)
        # Must produce output, not mutate governance
        assert result["ok"] is True
        state = Path(td) / "state"
        # governance log must not be created/modified by intelligence run
        gov_log = state / "drift_governance_log.jsonl"
        assert not gov_log.exists()

    def test_outputs_limited_to_ag37_files(self):
        td = _make_tmpdir()
        _write_jsonl(td, "drift_findings.jsonl", _sample_findings(3))
        from core.audit.drift_intelligence import run_drift_intelligence
        run_drift_intelligence(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        allowed = {
            "drift_findings.jsonl",
            "drift_intelligence_log.jsonl",
            "drift_intelligence_latest.json",
            "drift_pattern_registry.json",
            "runtime_stability_score.json",
        }
        unexpected = written - allowed
        assert not unexpected, f"unexpected files: {unexpected}"
