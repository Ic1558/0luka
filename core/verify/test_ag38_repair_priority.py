"""AG-38: Repair Priority Orchestration Layer — test suite.

Tests:
  A. Priority Policy Unit Tests
  B. Orchestrator Unit Tests
  C. Integration Tests
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
    path = Path(td) / "state" / "drift_finding_status.json"
    existing = json.loads(path.read_text()) if path.exists() else {}
    rec = {"status": status}
    if extra:
        rec.update(extra)
    existing[finding_id] = rec
    path.write_text(json.dumps(existing))


def _write_finding(td: str, finding: dict) -> None:
    path = Path(td) / "state" / "drift_findings.jsonl"
    with path.open("a") as fh:
        fh.write(json.dumps(finding) + "\n")


def _mock_request(body: dict[str, Any]) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


def _gate_regression_finding(fid: str = "f-gate") -> dict:
    return {
        "finding_id": fid,
        "status": "ESCALATED",
        "drift_type": "operator_gate_regression",
        "drift_class": "operator_gate_missing",
        "severity": "CRITICAL",
        "component": "interface/operator/api_test.py",
    }


def _naming_finding(fid: str = "f-name") -> dict:
    return {
        "finding_id": fid,
        "status": "OPEN",
        "drift_type": "naming_drift",
        "drift_class": "naming_drift_only",
        "severity": "LOW",
        "component": "core.test_module",
    }


# ---------------------------------------------------------------------------
# Suite A: Priority Policy
# ---------------------------------------------------------------------------

class TestPriorityPolicy:

    def test_classify_priority_returns_p1_for_high_score(self):
        from core.audit.priority_policy import classify_priority
        assert classify_priority(90) == "P1"
        assert classify_priority(85) == "P1"

    def test_classify_priority_returns_p2(self):
        from core.audit.priority_policy import classify_priority
        assert classify_priority(75) == "P2"
        assert classify_priority(70) == "P2"

    def test_classify_priority_returns_p3(self):
        from core.audit.priority_policy import classify_priority
        assert classify_priority(55) == "P3"
        assert classify_priority(50) == "P3"

    def test_classify_priority_returns_p4_for_low_score(self):
        from core.audit.priority_policy import classify_priority
        assert classify_priority(10) == "P4"
        assert classify_priority(0) == "P4"

    def test_all_four_priority_classes_defined(self):
        from core.audit.priority_policy import PRIORITY_CLASSES
        assert set(PRIORITY_CLASSES.keys()) == {"P1", "P2", "P3", "P4"}

    def test_priority_reason_codes_returns_dict(self):
        from core.audit.priority_policy import priority_reason_codes
        codes = priority_reason_codes()
        assert isinstance(codes, dict)
        assert "operator_gate_risk" in codes
        assert "escalated_status" in codes


# ---------------------------------------------------------------------------
# Suite B: Orchestrator Unit Tests
# ---------------------------------------------------------------------------

class TestOrchestratorUnit:

    def test_score_repair_priority_high_severity_recurring_gate_regression(self):
        from core.audit.repair_priority_orchestrator import score_repair_priority
        finding = _gate_regression_finding()
        result = score_repair_priority(
            finding,
            pattern_index={"recurring_operator_gate_regression": ["interface/operator/api_test.py"]},
        )
        assert result["priority_score"] >= 85
        assert result["priority_class"] == "P1"
        assert "operator_gate_risk" in result["reasons"]

    def test_score_repair_priority_low_for_naming_drift(self):
        from core.audit.repair_priority_orchestrator import score_repair_priority
        finding = _naming_finding()
        result = score_repair_priority(finding)
        assert result["priority_score"] < 85

    def test_priority_reasons_include_pattern_and_governance_risk(self):
        from core.audit.repair_priority_orchestrator import score_repair_priority
        finding = _gate_regression_finding()
        result = score_repair_priority(
            finding,
            pattern_index={"recurring_operator_gate_regression": ["interface/operator/api_test.py"]},
        )
        assert "operator_gate_risk" in result["reasons"]
        assert "recurring_pattern" in result["reasons"]

    def test_build_priority_queue_orders_by_score_desc(self):
        from core.audit.repair_priority_orchestrator import build_priority_queue
        findings = [
            _naming_finding("f-low"),
            _gate_regression_finding("f-high"),
            {"finding_id": "f-mid", "status": "ESCALATED", "drift_type": "wiring_gap",
             "severity": "MEDIUM", "component": "core.x"},
        ]
        queue = build_priority_queue(findings)
        scores = [item["priority_score"] for item in queue]
        assert scores == sorted(scores, reverse=True)
        assert queue[0]["recommended_order"] == 1

    def test_build_priority_queue_recommended_order_sequential(self):
        from core.audit.repair_priority_orchestrator import build_priority_queue
        findings = [_gate_regression_finding("a"), _naming_finding("b")]
        queue = build_priority_queue(findings)
        orders = [item["recommended_order"] for item in queue]
        assert orders == list(range(1, len(queue) + 1))

    def test_store_priority_queue_writes_json_and_jsonl(self):
        td = _make_tmpdir()
        from core.audit.repair_priority_orchestrator import store_priority_queue
        queue = [{"finding_id": "f1", "priority_score": 90, "priority_class": "P1"}]
        summary = {"ts": "2026-03-16T00:00:00Z", "total_items": 1}
        store_priority_queue(queue, summary, td)
        state = Path(td) / "state"
        assert (state / "repair_priority_queue.json").exists()
        assert (state / "repair_priority_log.jsonl").exists()
        assert (state / "repair_priority_latest.json").exists()

    def test_hotspot_bonus_applied(self):
        from core.audit.repair_priority_orchestrator import score_repair_priority
        finding = {"finding_id": "f1", "status": "OPEN", "severity": "MEDIUM",
                   "drift_type": "wiring_gap", "component": "hot.module"}
        no_hotspot = score_repair_priority(finding, hotspot_index={})
        with_hotspot = score_repair_priority(finding, hotspot_index={"hot.module": 6})
        assert with_hotspot["priority_score"] > no_hotspot["priority_score"]
        assert "hotspot_component" in with_hotspot["reasons"]

    def test_failed_repair_urgency_increases_score(self):
        from core.audit.repair_priority_orchestrator import score_repair_priority
        finding = {"finding_id": "f-fail", "status": "OPEN", "severity": "MEDIUM",
                   "drift_type": "wiring_gap", "component": "core.x"}
        no_fail = score_repair_priority(finding, failed_repair_index={})
        with_fail = score_repair_priority(finding, failed_repair_index={"f-fail": 3})
        assert with_fail["priority_score"] > no_fail["priority_score"]
        assert "failed_repair_history" in with_fail["reasons"]


# ---------------------------------------------------------------------------
# Suite C: Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_run_repair_priority_orchestration_generates_queue(self):
        td = _make_tmpdir()
        _write_status(td, "f-001", "ESCALATED")
        _write_finding(td, _gate_regression_finding("f-001"))
        from core.audit.repair_priority_orchestrator import run_repair_priority_orchestration
        result = run_repair_priority_orchestration(td)
        assert result["ok"] is True
        assert result["total_items"] >= 1

    def test_run_generates_all_three_output_files(self):
        td = _make_tmpdir()
        _write_status(td, "f-001", "ESCALATED")
        _write_finding(td, _gate_regression_finding("f-001"))
        from core.audit.repair_priority_orchestrator import run_repair_priority_orchestration
        run_repair_priority_orchestration(td)
        state = Path(td) / "state"
        assert (state / "repair_priority_queue.json").exists()
        assert (state / "repair_priority_log.jsonl").exists()
        assert (state / "repair_priority_latest.json").exists()

    def test_run_empty_findings_returns_empty_queue(self):
        td = _make_tmpdir()
        from core.audit.repair_priority_orchestrator import run_repair_priority_orchestration
        result = run_repair_priority_orchestration(td)
        assert result["ok"] is True
        assert result["total_items"] == 0
        assert result["top_priority"] is None

    def test_api_repair_priority_queue_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_priority import repair_priority_queue
        result = asyncio.run(repair_priority_queue())
        assert result["ok"] is True
        assert "queue" in result

    def test_api_repair_priority_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_priority import repair_priority_latest
        result = asyncio.run(repair_priority_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_repair_priority_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_priority import repair_priority_run
        req = _mock_request({})
        resp = asyncio.run(repair_priority_run(req))
        assert resp.status_code == 403

    def test_api_repair_priority_run_generates_outputs(self):
        td = _make_tmpdir()
        _write_status(td, "f-001", "ESCALATED")
        _write_finding(td, _gate_regression_finding("f-001"))
        from interface.operator.api_repair_priority import repair_priority_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(repair_priority_run(req))
        data = json.loads(resp.body)
        assert data["ok"] is True
        assert data["items"] >= 1

    def test_api_by_finding_id_not_in_queue_returns_error(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_priority import repair_priority_by_finding
        result = asyncio.run(repair_priority_by_finding("nonexistent"))
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_repair_priority_does_not_execute_repairs(self):
        td = _make_tmpdir()
        _write_status(td, "f-001", "ESCALATED")
        _write_finding(td, _gate_regression_finding("f-001"))
        from core.audit.repair_priority_orchestrator import run_repair_priority_orchestration
        run_repair_priority_orchestration(td)
        state = Path(td) / "state"
        assert not (state / "drift_repair_execution_log.jsonl").exists()

    def test_repair_priority_does_not_mutate_governance_state(self):
        td = _make_tmpdir()
        _write_status(td, "f-001", "ESCALATED")
        status_path = Path(td) / "state" / "drift_finding_status.json"
        mtime_before = status_path.stat().st_mtime
        from core.audit.repair_priority_orchestrator import run_repair_priority_orchestration
        run_repair_priority_orchestration(td)
        mtime_after = status_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_repair_priority_does_not_modify_baseline(self):
        td = _make_tmpdir()
        baseline_path = Path(__file__).parent.parent / "audit" / "audit_baseline.py"
        mtime_before = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        from core.audit.repair_priority_orchestrator import run_repair_priority_orchestration
        run_repair_priority_orchestration(td)
        mtime_after = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        assert mtime_before == mtime_after

    def test_repair_priority_is_ordering_only(self):
        td = _make_tmpdir()
        _write_status(td, "f-001", "ESCALATED")
        _write_finding(td, _gate_regression_finding("f-001"))
        from core.audit.repair_priority_orchestrator import run_repair_priority_orchestration
        run_repair_priority_orchestration(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        forbidden = {
            "drift_repair_execution_log.jsonl",
            "drift_governance_log.jsonl",
            "audit_baseline.py",
        }
        assert not (written & forbidden), f"forbidden files written: {written & forbidden}"

    def test_outputs_limited_to_ag38_files(self):
        td = _make_tmpdir()
        _write_status(td, "f-001", "OPEN")
        _write_finding(td, _naming_finding("f-001"))
        from core.audit.repair_priority_orchestrator import run_repair_priority_orchestration
        run_repair_priority_orchestration(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        allowed = {
            "drift_finding_status.json",
            "drift_findings.jsonl",
            "repair_priority_queue.json",
            "repair_priority_log.jsonl",
            "repair_priority_latest.json",
        }
        unexpected = written - allowed
        assert not unexpected, f"unexpected files: {unexpected}"
