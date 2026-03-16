"""AG-36: Baseline Realignment & Structural Drift Prevention — test suite.

Tests:
  A. Baseline Realigner — unit tests
  B. Structural Drift Guard — unit tests
  C. End-to-End Integration
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


def _write_status(td: str, finding_id: str, status: str, extra: dict | None = None) -> None:
    state = Path(td) / "state"
    path = state / "drift_finding_status.json"
    try:
        existing = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        existing = {}
    rec = {"status": status}
    if extra:
        rec.update(extra)
    existing[finding_id] = rec
    path.write_text(json.dumps(existing))


def _write_finding(td: str, finding: dict) -> None:
    state = Path(td) / "state"
    path = state / "drift_findings.jsonl"
    with path.open("a") as fh:
        fh.write(json.dumps(finding) + "\n")


def _write_recon(td: str, recon: dict) -> None:
    state = Path(td) / "state"
    path = state / "repair_reconciliation_log.jsonl"
    with path.open("a") as fh:
        fh.write(json.dumps(recon) + "\n")


def _mock_request(body: dict[str, Any]) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Baseline Realigner Unit Tests
# ---------------------------------------------------------------------------

class TestBaselineRealignerUnit:

    def test_list_reconciled_findings_excludes_open_or_escalated(self):
        td = _make_tmpdir()
        _write_status(td, "find-a", "ACCEPTED")
        _write_status(td, "find-b", "OPEN")
        _write_status(td, "find-c", "ESCALATED")
        _write_status(td, "find-d", "RESOLVED")
        from core.audit.baseline_realigner import list_reconciled_findings
        results = list_reconciled_findings(td)
        ids = {r["finding_id"] for r in results}
        assert "find-a" in ids
        assert "find-d" in ids
        assert "find-b" not in ids
        assert "find-c" not in ids

    def test_list_reconciled_findings_excludes_dismissed(self):
        td = _make_tmpdir()
        _write_status(td, "find-dismissed", "DISMISSED")
        from core.audit.baseline_realigner import list_reconciled_findings
        results = list_reconciled_findings(td)
        ids = {r["finding_id"] for r in results}
        assert "find-dismissed" not in ids

    def test_evaluate_baseline_eligibility_requires_reconciliation_status(self):
        from core.audit.baseline_realigner import evaluate_baseline_eligibility
        finding = {"finding_id": "f1", "status": "OPEN", "drift_type": "naming_drift"}
        result = evaluate_baseline_eligibility(finding)
        assert result["eligible"] is False

    def test_evaluate_baseline_eligibility_blocks_operator_gate_regression(self):
        from core.audit.baseline_realigner import evaluate_baseline_eligibility
        finding = {"finding_id": "f1", "status": "ACCEPTED", "drift_type": "operator_gate_regression"}
        result = evaluate_baseline_eligibility(finding)
        assert result["eligible"] is False

    def test_evaluate_baseline_eligibility_passes_accepted_naming_drift(self):
        from core.audit.baseline_realigner import evaluate_baseline_eligibility
        finding = {
            "finding_id": "f1",
            "status": "ACCEPTED",
            "drift_type": "naming_drift",
            "evidence": "module named differently",
            "reconciliation_id": "recon-abc",
        }
        result = evaluate_baseline_eligibility(finding)
        assert result["eligible"] is True
        assert result["confidence"] > 0.7

    def test_generate_baseline_proposal_contains_required_fields(self):
        from core.audit.baseline_realigner import generate_baseline_proposal
        finding = {
            "finding_id": "f1",
            "status": "ACCEPTED",
            "drift_type": "naming_drift",
            "evidence": "module named differently",
            "reconciliation_id": "recon-abc",
        }
        proposal = generate_baseline_proposal(finding)
        for field in ("ts", "proposal_id", "finding_id", "reconciliation_id", "proposal_type",
                      "target_artifacts", "rationale", "evidence_refs",
                      "operator_action_required", "status", "confidence"):
            assert field in proposal, f"missing field: {field}"
        assert proposal["operator_action_required"] is True
        assert proposal["status"] == "PROPOSED"

    def test_generate_baseline_proposal_raises_for_ineligible(self):
        from core.audit.baseline_realigner import generate_baseline_proposal
        finding = {"finding_id": "f1", "status": "OPEN", "drift_type": "naming_drift"}
        with pytest.raises(ValueError, match="not eligible"):
            generate_baseline_proposal(finding)

    def test_store_baseline_proposal_appends_jsonl(self):
        td = _make_tmpdir()
        from core.audit.baseline_realigner import store_baseline_proposal, list_all_proposals
        proposal = {"proposal_id": "prop-001", "status": "PROPOSED", "operator_action_required": True}
        store_baseline_proposal(proposal, td)
        store_baseline_proposal(proposal, td)
        proposals = list_all_proposals(td)
        assert len(proposals) == 2

    def test_run_baseline_realignment_empty_returns_zero(self):
        td = _make_tmpdir()
        from core.audit.baseline_realigner import run_baseline_realignment
        summary = run_baseline_realignment(td)
        assert summary["proposals_generated"] == 0
        assert summary["findings_evaluated"] == 0

    def test_run_baseline_realignment_generates_proposals(self):
        td = _make_tmpdir()
        _write_status(td, "find-001", "ACCEPTED")
        _write_finding(td, {
            "id": "find-001",
            "finding_id": "find-001",
            "drift_type": "naming_drift",
            "drift_class": "naming_drift_only",
            "component": "core.runtime_guardian",
            "evidence": "module named circuit_breaker",
        })
        _write_recon(td, {
            "reconciliation_id": "recon-001",
            "finding_id": "find-001",
            "drift_state": "DRIFT_CLEARED",
            "governance_recommendation": "recommend_RESOLVED",
        })
        from core.audit.baseline_realigner import run_baseline_realignment
        summary = run_baseline_realignment(td)
        assert summary["proposals_generated"] >= 1
        assert summary["findings_evaluated"] >= 1


# ---------------------------------------------------------------------------
# Suite B: Structural Drift Guard Unit Tests
# ---------------------------------------------------------------------------

class TestStructuralDriftGuardUnit:

    def test_detect_recurring_drift_patterns_groups_similar_findings(self):
        from core.audit.structural_drift_guard import detect_recurring_drift_patterns
        findings = [
            {"id": "f1", "drift_class": "naming_drift_only", "component": "core.a"},
            {"id": "f2", "drift_class": "naming_drift_only", "component": "core.b"},
            {"id": "f3", "drift_class": "naming_drift_only", "component": "core.c"},
        ]
        patterns = detect_recurring_drift_patterns(findings)
        assert len(patterns) >= 1
        classes = {p["pattern_class"] for p in patterns}
        assert "recurring_naming_drift" in classes

    def test_detect_recurring_drift_patterns_excludes_single_occurrence(self):
        from core.audit.structural_drift_guard import detect_recurring_drift_patterns
        findings = [
            {"id": "f1", "drift_class": "naming_drift_only", "component": "core.a"},
        ]
        patterns = detect_recurring_drift_patterns(findings)
        assert len(patterns) == 0

    def test_classify_structural_drift_returns_pattern_class(self):
        from core.audit.structural_drift_guard import classify_structural_drift
        pattern = {
            "pattern_id": "pattern-001",
            "pattern_class": "recurring_route_surface_drift",
            "affected_components": ["GET /api/x", "GET /api/y"],
            "count": 3,
            "severity": "MEDIUM",
        }
        result = classify_structural_drift(pattern)
        assert result["pattern_class"] == "recurring_route_surface_drift"
        assert "prevention_suggestions" in result
        assert len(result["prevention_suggestions"]) > 0
        assert result["operator_action_required"] is True

    def test_classify_structural_drift_high_severity_for_5plus(self):
        from core.audit.structural_drift_guard import classify_structural_drift
        pattern = {"pattern_id": "p", "pattern_class": "recurring_operator_gate_regression",
                   "affected_components": ["a", "b", "c", "d", "e"], "count": 5, "severity": "HIGH"}
        result = classify_structural_drift(pattern)
        assert result["structural_risk"] == "HIGH"

    def test_all_six_pattern_classes_are_detectable(self):
        from core.audit.structural_drift_guard import detect_recurring_drift_patterns
        findings = [
            {"drift_class": "naming_drift_only", "component": "a"},
            {"drift_class": "naming_drift_only", "component": "b"},
            {"drift_class": "API_exposed_but_not_in_diagram", "component": "c"},
            {"drift_class": "API_exposed_but_not_in_diagram", "component": "d"},
            {"drift_class": "operator_gate_missing", "component": "e"},
            {"drift_class": "operator_gate_missing", "component": "f"},
            {"drift_class": "state_file_expected_but_not_produced", "component": "g"},
            {"drift_class": "state_file_expected_but_not_produced", "component": "h"},
            {"drift_class": "legacy_component_still_active", "component": "i"},
            {"drift_class": "legacy_component_still_active", "component": "j"},
            {"drift_class": "exists_but_not_wired", "component": "k"},
            {"drift_class": "exists_but_not_wired", "component": "l"},
        ]
        patterns = detect_recurring_drift_patterns(findings)
        classes = {p["pattern_class"] for p in patterns}
        expected = {
            "recurring_naming_drift",
            "recurring_route_surface_drift",
            "recurring_operator_gate_regression",
            "recurring_state_file_absence",
            "recurring_legacy_overlap",
            "recurring_baseline_mismatch",
        }
        assert expected == classes

    def test_store_and_list_patterns(self):
        td = _make_tmpdir()
        from core.audit.structural_drift_guard import store_drift_patterns, list_all_patterns
        pattern = {"pattern_id": "p-001", "pattern_class": "recurring_naming_drift", "count": 2}
        store_drift_patterns([pattern], td)
        patterns = list_all_patterns(td)
        assert len(patterns) == 1
        assert patterns[0]["pattern_class"] == "recurring_naming_drift"


# ---------------------------------------------------------------------------
# Suite C: End-to-End Integration
# ---------------------------------------------------------------------------

class TestEndToEndIntegration:

    def test_api_proposals_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_baseline_realign import baseline_realign_proposals
        result = asyncio.run(baseline_realign_proposals())
        assert result["ok"] is True
        assert "proposals" in result

    def test_api_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_baseline_realign import baseline_realign_latest
        result = asyncio.run(baseline_realign_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_patterns_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_baseline_realign import baseline_realign_patterns
        result = asyncio.run(baseline_realign_patterns())
        assert result["ok"] is True
        assert "patterns" in result

    def test_api_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_baseline_realign import baseline_realign_run
        req = _mock_request({})
        resp = asyncio.run(baseline_realign_run(req))
        assert resp.status_code == 403

    def test_api_baseline_realign_run_generates_proposals(self):
        td = _make_tmpdir()
        _write_status(td, "find-001", "ACCEPTED")
        _write_finding(td, {
            "id": "find-001",
            "finding_id": "find-001",
            "drift_type": "naming_drift",
            "component": "core.runtime_guardian",
            "evidence": "module mismatch",
        })
        _write_recon(td, {
            "reconciliation_id": "recon-001",
            "finding_id": "find-001",
            "drift_state": "DRIFT_CLEARED",
        })
        from interface.operator.api_baseline_realign import baseline_realign_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(baseline_realign_run(req))
        data = json.loads(resp.body)
        assert data["ok"] is True
        assert data["proposals_generated"] >= 1

    def test_patterns_endpoint_returns_detected_patterns(self):
        td = _make_tmpdir()
        # Write some findings that trigger patterns
        for i in range(3):
            _write_finding(td, {
                "id": f"f{i}",
                "drift_class": "naming_drift_only",
                "component": f"core.module_{i}",
            })
        from core.audit.structural_drift_guard import detect_and_store_patterns
        detect_and_store_patterns(td)
        from interface.operator.api_baseline_realign import baseline_realign_patterns
        result = asyncio.run(baseline_realign_patterns())
        assert result["ok"] is True
        assert result["total"] >= 1


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_baseline_realigner_does_not_modify_audit_baseline_file(self):
        td = _make_tmpdir()
        baseline_path = Path(__file__).parent.parent / "audit" / "audit_baseline.py"
        mtime_before = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        _write_status(td, "find-001", "ACCEPTED")
        _write_finding(td, {"id": "find-001", "finding_id": "find-001", "drift_type": "naming_drift",
                             "evidence": "x", "component": "core.x"})
        from core.audit.baseline_realigner import run_baseline_realignment
        run_baseline_realignment(td)
        mtime_after = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        assert mtime_before == mtime_after

    def test_baseline_realigner_does_not_edit_architecture_docs(self):
        td = _make_tmpdir()
        arch_path = Path(__file__).parent.parent.parent / "g" / "reports" / "architecture" / "0luka_architecture_diagram_ag30.md"
        mtime_before = arch_path.stat().st_mtime if arch_path.exists() else 0
        _write_status(td, "find-001", "ACCEPTED")
        _write_finding(td, {"id": "find-001", "finding_id": "find-001",
                             "drift_type": "diagram_mismatch", "evidence": "y", "component": "core.y"})
        from core.audit.baseline_realigner import run_baseline_realignment
        run_baseline_realignment(td)
        mtime_after = arch_path.stat().st_mtime if arch_path.exists() else 0
        assert mtime_before == mtime_after

    def test_baseline_realigner_does_not_change_finding_status(self):
        td = _make_tmpdir()
        _write_status(td, "find-001", "ACCEPTED")
        state_path = Path(td) / "state" / "drift_finding_status.json"
        mtime_before = state_path.stat().st_mtime
        from core.audit.baseline_realigner import run_baseline_realignment
        run_baseline_realignment(td)
        mtime_after = state_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_baseline_realigner_is_proposal_only(self):
        td = _make_tmpdir()
        _write_status(td, "find-001", "ACCEPTED")
        _write_finding(td, {"id": "find-001", "finding_id": "find-001",
                             "drift_type": "naming_drift", "evidence": "z",
                             "reconciliation_id": "recon-001"})
        from core.audit.baseline_realigner import run_baseline_realignment, list_all_proposals
        run_baseline_realignment(td)
        proposals = list_all_proposals(td)
        assert all(p["status"] == "PROPOSED" for p in proposals)
        assert all(p["operator_action_required"] is True for p in proposals)

    def test_structural_drift_guard_does_not_modify_any_source_files(self):
        td = _make_tmpdir()
        for i in range(3):
            _write_finding(td, {"id": f"f{i}", "drift_class": "naming_drift_only",
                                 "component": f"core.mod_{i}"})
        baseline_path = Path(__file__).parent.parent / "audit" / "audit_baseline.py"
        mtime_before = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        from core.audit.structural_drift_guard import detect_and_store_patterns
        detect_and_store_patterns(td)
        mtime_after = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        assert mtime_before == mtime_after

    def test_outputs_limited_to_ag36_files(self):
        td = _make_tmpdir()
        _write_status(td, "find-001", "ACCEPTED")
        _write_finding(td, {"id": "find-001", "finding_id": "find-001",
                             "drift_type": "naming_drift", "evidence": "e"})
        from core.audit.baseline_realigner import run_baseline_realignment
        from core.audit.structural_drift_guard import detect_and_store_patterns
        run_baseline_realignment(td)
        detect_and_store_patterns(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        allowed = {
            "drift_finding_status.json",
            "drift_findings.jsonl",
            "baseline_realign_proposals.jsonl",
            "baseline_realign_latest.json",
            "structural_drift_patterns.jsonl",
        }
        unexpected = written - allowed
        assert not unexpected, f"unexpected files written: {unexpected}"
