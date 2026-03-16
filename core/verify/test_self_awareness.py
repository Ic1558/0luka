"""AG-47: Runtime Self-Awareness System — test suite.

Tests:
  A. Self-Awareness Policy Unit Tests
  B. Self-Awareness System Unit Tests
  C. Integration Tests
  D. Safety Invariants
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
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


def _write_strategy(td: str, mode: str = "CONSERVATIVE") -> None:
    (Path(td) / "state" / "runtime_operating_mode.json").write_text(
        json.dumps({"operating_mode": mode, "confidence": 0.82})
    )
    (Path(td) / "state" / "runtime_strategy_latest.json").write_text(
        json.dumps({"operating_mode": mode, "key_risks": [], "recommendations": []})
    )


def _write_governance(td: str, findings: int = 2) -> None:
    status = {f"f-{i:03d}": {"status": "OPEN"} for i in range(findings)}
    (Path(td) / "state" / "drift_finding_status.json").write_text(json.dumps(status))


def _write_decision_queue(td: str) -> None:
    (Path(td) / "state" / "decision_queue_governance_latest.json").write_text(
        json.dumps({
            "open_count": 2, "urgent_count": 1,
            "operator_action_required": True, "queue": []
        })
    )


def _write_capabilities(td: str, caps: list[str]) -> None:
    path = Path(td) / "state" / "runtime_capabilities.jsonl"
    with path.open("w") as f:
        for cap in caps:
            f.write(json.dumps({
                "capability_id": cap, "component": "AG-XX",
                "activation_source": "test", "activated_at": "2026-03-16T00:00:00Z",
                "status": "ACTIVE", "notes": "",
            }) + "\n")


def _mock_request(body: dict) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Policy Unit Tests
# ---------------------------------------------------------------------------

class TestSelfAwarenessPolicy:

    def test_readiness_classes_defined(self):
        from runtime.self_awareness_policy import READINESS_CLASSES
        required = {"LIMITED", "PARTIAL", "OPERATIONAL", "SUPERVISED_READY", "GOVERNED_READY"}
        assert required.issubset(set(READINESS_CLASSES))

    def test_classify_readiness_governed_ready_full_stack(self):
        from runtime.self_awareness_policy import classify_readiness
        result = classify_readiness({
            "active_capability_count": 10,
            "strategy_active":         True,
            "governance_active":       True,
            "decision_queue_active":   True,
            "repair_active":           True,
        })
        assert result == "GOVERNED_READY"

    def test_classify_readiness_limited_no_capabilities(self):
        from runtime.self_awareness_policy import classify_readiness
        result = classify_readiness({"active_capability_count": 0})
        assert result == "LIMITED"

    def test_classify_readiness_partial_some_capabilities(self):
        from runtime.self_awareness_policy import classify_readiness
        result = classify_readiness({"active_capability_count": 3})
        assert result == "PARTIAL"

    def test_classify_governance_posture_operator_gated(self):
        from runtime.self_awareness_policy import classify_governance_posture
        result = classify_governance_posture({"operator_action_required": True})
        assert result == "OPERATOR_GATED"

    def test_classify_governance_posture_absent(self):
        from runtime.self_awareness_policy import classify_governance_posture
        result = classify_governance_posture({})
        assert result == "GOVERNANCE_ABSENT"

    def test_classify_repair_posture_supervised_available(self):
        from runtime.self_awareness_policy import classify_repair_posture
        result = classify_repair_posture({
            "repair_plan_present": True,
            "repair_execution_available": True,
        })
        assert result == "SUPERVISED_REPAIR_AVAILABLE"

    def test_classify_repair_posture_absent(self):
        from runtime.self_awareness_policy import classify_repair_posture
        result = classify_repair_posture({})
        assert result == "REPAIR_ABSENT"


# ---------------------------------------------------------------------------
# Suite B: Self-Awareness Unit Tests
# ---------------------------------------------------------------------------

class TestSelfAwarenessUnit:

    def test_derive_runtime_identity_contains_required_fields(self):
        td = _make_tmpdir()
        from runtime.self_awareness import derive_runtime_identity
        cap_data = {"active_count": 5, "active_capabilities": ["cap_a", "cap_b"]}
        strat_data = {"operating_mode": "CONSERVATIVE", "strategy_present": True}
        identity = derive_runtime_identity(cap_data, strat_data)
        required = {"system_identity", "runtime_role", "active_capability_count"}
        assert required.issubset(set(identity.keys()))
        assert identity["system_identity"] == "Supervised Agentic Runtime Platform"

    def test_derive_runtime_readiness_returns_governed_ready_when_stack_active(self):
        td = _make_tmpdir()
        from runtime.self_awareness import derive_runtime_readiness
        result = derive_runtime_readiness(
            capability_data={"active_count": 10, "active_capabilities": []},
            strategy_data={"strategy_present": True, "operating_mode": "CONSERVATIVE"},
            decision_data={"queue_governance_present": True, "decision_assist_present": True,
                           "operator_action_required": True},
            governance_data={"governance_present": True, "findings_count": 2},
            repair_data={"repair_plan_present": True, "repair_execution_available": True},
        )
        assert result["readiness"] == "GOVERNED_READY"
        assert "confidence" in result
        assert isinstance(result["reasons"], list)
        assert len(result["reasons"]) >= 1

    def test_derive_runtime_posture_contains_required_sections(self):
        td = _make_tmpdir()
        from runtime.self_awareness import derive_runtime_posture
        posture = derive_runtime_posture(
            strategy_data={"strategy_present": True, "operating_mode": "CONSERVATIVE"},
            governance_data={"findings_count": 1, "governance_present": True},
            repair_data={"repair_plan_present": True, "repair_execution_available": True},
            campaign_data={"campaign_present": True, "outcome_intel_present": True},
            decision_data={"queue_governance_present": True, "decision_assist_present": True,
                           "operator_action_required": True},
        )
        required = {"operating_mode", "governance_posture", "repair_posture",
                    "campaign_posture", "decision_posture"}
        assert required.issubset(set(posture.keys()))

    def test_build_self_awareness_report_contains_evidence_refs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        from runtime.self_awareness import build_self_awareness_report
        report = build_self_awareness_report(td)
        assert "evidence_refs" in report
        assert len(report["evidence_refs"]) >= 1

    def test_build_self_awareness_report_required_top_level_fields(self):
        td = _make_tmpdir()
        from runtime.self_awareness import build_self_awareness_report
        report = build_self_awareness_report(td)
        required = {"ts", "run_id", "identity", "readiness", "posture",
                    "critical_gaps", "evidence_refs"}
        assert required.issubset(set(report.keys()))

    def test_store_self_awareness_writes_outputs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        from runtime.self_awareness import build_self_awareness_report, store_self_awareness
        report = build_self_awareness_report(td)
        store_self_awareness(report, td)
        state = Path(td) / "state"
        assert (state / "runtime_self_awareness_log.jsonl").exists()
        assert (state / "runtime_self_awareness_latest.json").exists()
        assert (state / "runtime_readiness.json").exists()


# ---------------------------------------------------------------------------
# Suite C: Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_run_self_awareness_generates_outputs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        from runtime.self_awareness import run_self_awareness
        result = run_self_awareness(td)
        assert result["ok"] is True
        assert result["readiness"] is not None

    def test_run_generates_three_output_files(self):
        td = _make_tmpdir()
        from runtime.self_awareness import run_self_awareness
        run_self_awareness(td)
        state = Path(td) / "state"
        assert (state / "runtime_self_awareness_log.jsonl").exists()
        assert (state / "runtime_self_awareness_latest.json").exists()
        assert (state / "runtime_readiness.json").exists()

    def test_run_with_full_stack_returns_governed_ready(self):
        td = _make_tmpdir()
        _write_strategy(td, "CONSERVATIVE")
        _write_governance(td)
        _write_decision_queue(td)
        _write_capabilities(td, [f"cap_{i}" for i in range(9)])
        from runtime.self_awareness import run_self_awareness
        result = run_self_awareness(td)
        assert result["ok"] is True
        assert result["readiness"] == "GOVERNED_READY"

    def test_run_empty_state_defaults_gracefully(self):
        td = _make_tmpdir()
        from runtime.self_awareness import run_self_awareness
        result = run_self_awareness(td)
        assert result["ok"] is True
        assert result["readiness"] == "LIMITED"

    def test_api_self_awareness_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_self_awareness import self_awareness_latest
        result = asyncio.run(self_awareness_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_self_awareness_readiness_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_self_awareness import self_awareness_readiness
        result = asyncio.run(self_awareness_readiness())
        assert result["ok"] is True
        assert "readiness" in result

    def test_api_self_awareness_posture_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_self_awareness import self_awareness_posture
        result = asyncio.run(self_awareness_posture())
        assert result["ok"] is True
        assert "posture" in result

    def test_api_self_awareness_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_self_awareness import self_awareness_run
        req = _mock_request({})
        resp = asyncio.run(self_awareness_run(req))
        assert resp.status_code == 403

    def test_api_self_awareness_run_generates_outputs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        from interface.operator.api_self_awareness import self_awareness_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(self_awareness_run(req))
        data = json.loads(resp.body)
        assert data["ok"] is True
        assert "readiness" in data


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_self_awareness_does_not_mutate_governance_state(self):
        td = _make_tmpdir()
        _write_governance(td)
        gov_path = Path(td) / "state" / "drift_finding_status.json"
        mtime_before = gov_path.stat().st_mtime
        from runtime.self_awareness import run_self_awareness
        run_self_awareness(td)
        assert gov_path.stat().st_mtime == mtime_before

    def test_self_awareness_does_not_mutate_campaign_state(self):
        td = _make_tmpdir()
        camp_path = Path(td) / "state" / "repair_campaign_latest.json"
        camp_path.write_text(json.dumps({"campaigns": []}))
        mtime_before = camp_path.stat().st_mtime
        from runtime.self_awareness import run_self_awareness
        run_self_awareness(td)
        assert camp_path.stat().st_mtime == mtime_before

    def test_self_awareness_does_not_execute_repairs(self):
        td = _make_tmpdir()
        from runtime.self_awareness import run_self_awareness
        run_self_awareness(td)
        state = Path(td) / "state"
        assert not (state / "drift_repair_execution_log.jsonl").exists()

    def test_self_awareness_is_descriptive_only(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_governance(td)
        _write_capabilities(td, ["cap_a", "cap_b"])
        from runtime.self_awareness import run_self_awareness
        run_self_awareness(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        forbidden = {
            "drift_repair_execution_log.jsonl",
            "drift_governance_log.jsonl",
            "audit_baseline.py",
            "repair_campaign_log.jsonl",
            "decision_queue_state.json",
            "decision_queue_log.jsonl",
            "operator_decision_queue.json",
        }
        assert not (written & forbidden), f"forbidden files written: {written & forbidden}"

    def test_self_awareness_does_not_activate_capabilities(self):
        td = _make_tmpdir()
        cap_path = Path(td) / "state" / "runtime_capabilities.jsonl"
        from runtime.self_awareness import run_self_awareness
        run_self_awareness(td)
        # If no capabilities were registered before, none should be after
        if cap_path.exists():
            lines = [l for l in cap_path.read_text().splitlines() if l.strip()]
            assert len(lines) == 0
        # (file may not exist — that's also fine)
