"""AG-43: Operator Decision Assist Layer — test suite.

Tests:
  A. Decision Package Policy Unit Tests
  B. Decision Assist Unit Tests
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


def _write_strategy(td: str, mode: str = "CONSERVATIVE", recs: list | None = None) -> None:
    path = Path(td) / "state" / "runtime_strategy_latest.json"
    path.write_text(json.dumps({
        "operating_mode": mode,
        "mode_confidence": 0.82,
        "mode_reasons": [f"stability_{mode.lower()}"],
        "key_risks": ["stability_degraded"],
        "recommendations": recs or [],
        "recommendation_count": len(recs or []),
    }))
    mode_path = Path(td) / "state" / "runtime_operating_mode.json"
    mode_path.write_text(json.dumps({
        "operating_mode": mode,
        "confidence": 0.82,
        "reasons": [f"stability_{mode.lower()}"],
        "key_risks": ["stability_degraded"],
    }))


def _write_wave_schedule(td: str, waves: list | None = None) -> None:
    ws = waves or [{
        "wave_id": "wave-test-001",
        "wave_number": 1,
        "status": "PROPOSED",
        "items": [{"finding_id": "f-001", "priority_class": "P1"}],
        "item_count": 1,
        "priority_classes_present": ["P1"],
        "ts_created": "2026-03-16T00:00:00Z",
        "operator_action_required": True,
    }]
    path = Path(td) / "state" / "repair_wave_schedule.json"
    path.write_text(json.dumps({"waves": ws, "deferred_items": 0}))


def _write_governance_state(td: str, escalated: int = 0) -> None:
    status = {f"f-{i:03d}": {"status": "ESCALATED"} for i in range(escalated)}
    path = Path(td) / "state" / "drift_finding_status.json"
    path.write_text(json.dumps(status))


def _mock_request(body: dict) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Decision Package Policy Unit Tests
# ---------------------------------------------------------------------------

class TestDecisionPackagePolicy:

    def test_decision_types_minimum_defined(self):
        from core.audit.decision_package_policy import DECISION_TYPES
        required = {"APPROVE_REPAIR_WAVE", "DEFER_REPAIR_WAVE", "PAUSE_NEW_CAMPAIGNS",
                    "REVIEW_PATTERN_REUSE", "ACCEPT_BASELINE_PROPOSAL",
                    "REJECT_BASELINE_PROPOSAL", "ESCALATE_HIGH_RISK_COMPONENT",
                    "REQUIRE_GOVERNANCE_REVIEW"}
        assert required.issubset(set(DECISION_TYPES.keys()))

    def test_valid_decision_type_known(self):
        from core.audit.decision_package_policy import valid_decision_type
        assert valid_decision_type("APPROVE_REPAIR_WAVE") is True

    def test_valid_decision_type_unknown(self):
        from core.audit.decision_package_policy import valid_decision_type
        assert valid_decision_type("MAKE_COFFEE") is False

    def test_recommendation_to_decision_type_maps_known(self):
        from core.audit.decision_package_policy import recommendation_to_decision_type
        assert recommendation_to_decision_type("PAUSE_NEW_CAMPAIGNS") == "PAUSE_NEW_CAMPAIGNS"
        assert recommendation_to_decision_type("CONTINUE_REPAIR_WAVE") == "APPROVE_REPAIR_WAVE"
        assert recommendation_to_decision_type("REDUCE_WAVE_SIZE") == "DEFER_REPAIR_WAVE"

    def test_recommendation_to_decision_type_unknown_returns_none(self):
        from core.audit.decision_package_policy import recommendation_to_decision_type
        assert recommendation_to_decision_type("NONEXISTENT") is None

    def test_classify_decision_priority_critical_on_stabilize(self):
        from core.audit.decision_package_policy import classify_decision_priority
        prio = classify_decision_priority({
            "operating_mode": "STABILIZE",
            "decision_type": "REQUIRE_GOVERNANCE_REVIEW",
        })
        assert prio == "CRITICAL"

    def test_classify_decision_priority_high_on_regressions(self):
        from core.audit.decision_package_policy import classify_decision_priority
        prio = classify_decision_priority({
            "operating_mode": "REPAIR_FOCUSED",
            "active_regressions": 3,
            "decision_type": "APPROVE_REPAIR_WAVE",
        })
        assert prio == "HIGH"


# ---------------------------------------------------------------------------
# Suite B: Decision Assist Unit Tests
# ---------------------------------------------------------------------------

class TestDecisionAssistUnit:

    def test_build_decision_candidates_emits_repair_wave_approval_candidate(self):
        td = _make_tmpdir()
        _write_strategy(td, "REPAIR_FOCUSED")
        _write_wave_schedule(td)
        from core.audit.operator_decision_assist import (
            load_runtime_strategy, load_drift_governance_state,
            load_repair_priority, load_campaign_outcomes,
            load_repair_wave_state, build_decision_candidates,
        )
        strategy   = load_runtime_strategy(td)
        governance = load_drift_governance_state(td)
        priority   = load_repair_priority(td)
        outcomes   = load_campaign_outcomes(td)
        wave_state = load_repair_wave_state(td)
        candidates = build_decision_candidates(strategy, governance, priority, outcomes, wave_state)
        dtypes = [c["decision_type"] for c in candidates]
        assert "APPROVE_REPAIR_WAVE" in dtypes or "DEFER_REPAIR_WAVE" in dtypes

    def test_generate_decision_package_contains_required_fields(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_wave_schedule(td)
        from core.audit.operator_decision_assist import (
            load_runtime_strategy, load_repair_priority,
            build_decision_candidates, load_drift_governance_state,
            load_campaign_outcomes, load_repair_wave_state, generate_decision_package,
        )
        strategy   = load_runtime_strategy(td)
        governance = load_drift_governance_state(td)
        priority   = load_repair_priority(td)
        outcomes   = load_campaign_outcomes(td)
        wave_state = load_repair_wave_state(td)
        candidates = build_decision_candidates(strategy, governance, priority, outcomes, wave_state)
        assert candidates, "need at least one candidate"
        pkg = generate_decision_package(candidates[0], strategy, priority)
        required = {"ts", "decision_id", "decision_type", "target_ref", "operating_mode",
                    "summary", "rationale", "risks", "evidence_refs", "alternatives",
                    "recommended_action", "operator_action_required", "status"}
        assert required.issubset(set(pkg.keys()))

    def test_decision_package_includes_risks_alternatives_and_evidence(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_wave_schedule(td)
        from core.audit.operator_decision_assist import (
            load_runtime_strategy, load_repair_priority,
            build_decision_candidates, load_drift_governance_state,
            load_campaign_outcomes, load_repair_wave_state, generate_decision_package,
        )
        strategy   = load_runtime_strategy(td)
        governance = load_drift_governance_state(td)
        priority   = load_repair_priority(td)
        outcomes   = load_campaign_outcomes(td)
        wave_state = load_repair_wave_state(td)
        candidates = build_decision_candidates(strategy, governance, priority, outcomes, wave_state)
        pkg = generate_decision_package(candidates[0], strategy, priority)
        assert isinstance(pkg["risks"], list)
        assert isinstance(pkg["alternatives"], list)
        assert isinstance(pkg["evidence_refs"], list)
        assert len(pkg["evidence_refs"]) >= 1
        assert pkg["operator_action_required"] is True
        assert pkg["status"] == "PROPOSED"

    def test_build_decision_assist_report_contains_required_sections(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_wave_schedule(td)
        from core.audit.operator_decision_assist import build_decision_assist_report
        report = build_decision_assist_report(td)
        required = {"ts", "run_id", "operating_mode", "pending_decisions", "urgent_count",
                    "deferred_count", "packages", "type_distribution", "top_decision",
                    "key_risks", "operator_action_required"}
        assert required.issubset(set(report.keys()))
        assert report["operator_action_required"] is True

    def test_store_decision_assist_writes_three_outputs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        from core.audit.operator_decision_assist import build_decision_assist_report, store_decision_assist
        report = build_decision_assist_report(td)
        store_decision_assist(report, td)
        state = Path(td) / "state"
        assert (state / "operator_decision_packages.jsonl").exists()
        assert (state / "operator_decision_latest.json").exists()
        assert (state / "operator_decision_queue.json").exists()

    def test_decision_candidates_sorted_critical_first(self):
        td = _make_tmpdir()
        _write_strategy(td, "STABILIZE")
        _write_wave_schedule(td)
        _write_governance_state(td, escalated=5)
        from core.audit.operator_decision_assist import (
            load_runtime_strategy, load_drift_governance_state,
            load_repair_priority, load_campaign_outcomes,
            load_repair_wave_state, build_decision_candidates,
        )
        strategy   = load_runtime_strategy(td)
        governance = load_drift_governance_state(td)
        priority   = load_repair_priority(td)
        outcomes   = load_campaign_outcomes(td)
        wave_state = load_repair_wave_state(td)
        candidates = build_decision_candidates(strategy, governance, priority, outcomes, wave_state)
        prio_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        prios = [prio_order.get(c["priority"], 99) for c in candidates]
        assert prios == sorted(prios)

    def test_all_packages_have_operator_action_required(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_wave_schedule(td)
        from core.audit.operator_decision_assist import build_decision_assist_report
        report = build_decision_assist_report(td)
        for pkg in report["packages"]:
            assert pkg["operator_action_required"] is True


# ---------------------------------------------------------------------------
# Suite C: Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_run_operator_decision_assist_generates_outputs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_wave_schedule(td)
        from core.audit.operator_decision_assist import run_operator_decision_assist
        result = run_operator_decision_assist(td)
        assert result["ok"] is True
        assert result["operating_mode"] is not None

    def test_run_generates_all_three_output_files(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_wave_schedule(td)
        from core.audit.operator_decision_assist import run_operator_decision_assist
        run_operator_decision_assist(td)
        state = Path(td) / "state"
        assert (state / "operator_decision_packages.jsonl").exists()
        assert (state / "operator_decision_latest.json").exists()
        assert (state / "operator_decision_queue.json").exists()

    def test_run_no_inputs_defaults_gracefully(self):
        td = _make_tmpdir()
        from core.audit.operator_decision_assist import run_operator_decision_assist
        result = run_operator_decision_assist(td)
        assert result["ok"] is True

    def test_api_decision_assist_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_assist import decision_assist_latest
        result = asyncio.run(decision_assist_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_decision_assist_queue_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_assist import decision_assist_queue
        result = asyncio.run(decision_assist_queue())
        assert result["ok"] is True
        assert "packages" in result

    def test_api_decision_assist_summary_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_assist import decision_assist_summary
        result = asyncio.run(decision_assist_summary())
        assert result["ok"] is True
        assert "pending_decisions" in result

    def test_api_decision_assist_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_assist import decision_assist_run
        req = _mock_request({})
        resp = asyncio.run(decision_assist_run(req))
        assert resp.status_code == 403

    def test_api_decision_assist_run_generates_outputs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_wave_schedule(td)
        from interface.operator.api_decision_assist import decision_assist_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(decision_assist_run(req))
        data = json.loads(resp.body)
        assert data["ok"] is True
        assert data["operating_mode"] is not None

    def test_api_decision_assist_by_id_not_found(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_assist import decision_assist_by_id
        result = asyncio.run(decision_assist_by_id("decision-nonexistent"))
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_operator_decision_assist_does_not_mutate_governance_state(self):
        td = _make_tmpdir()
        _write_governance_state(td, escalated=2)
        _write_strategy(td)
        gov_path = Path(td) / "state" / "drift_finding_status.json"
        mtime_before = gov_path.stat().st_mtime
        from core.audit.operator_decision_assist import run_operator_decision_assist
        run_operator_decision_assist(td)
        assert gov_path.stat().st_mtime == mtime_before

    def test_operator_decision_assist_does_not_execute_repairs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        from core.audit.operator_decision_assist import run_operator_decision_assist
        run_operator_decision_assist(td)
        state = Path(td) / "state"
        assert not (state / "drift_repair_execution_log.jsonl").exists()

    def test_operator_decision_assist_does_not_modify_baseline(self):
        td = _make_tmpdir()
        _write_strategy(td)
        baseline_path = Path(__file__).parent.parent / "audit" / "audit_baseline.py"
        mtime_before = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        from core.audit.operator_decision_assist import run_operator_decision_assist
        run_operator_decision_assist(td)
        mtime_after = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        assert mtime_before == mtime_after

    def test_operator_decision_assist_is_assist_only(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_wave_schedule(td)
        from core.audit.operator_decision_assist import run_operator_decision_assist
        run_operator_decision_assist(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        forbidden = {
            "drift_repair_execution_log.jsonl",
            "drift_governance_log.jsonl",
            "audit_baseline.py",
            "repair_campaign_log.jsonl",
        }
        assert not (written & forbidden), f"forbidden files written: {written & forbidden}"

    def test_outputs_limited_to_ag43_files(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_wave_schedule(td)
        from core.audit.operator_decision_assist import run_operator_decision_assist
        run_operator_decision_assist(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        allowed = {
            # pre-existing inputs written by test helpers
            "runtime_strategy_latest.json",
            "runtime_operating_mode.json",
            "repair_wave_schedule.json",
            # AG-43 outputs
            "operator_decision_packages.jsonl",
            "operator_decision_latest.json",
            "operator_decision_queue.json",
        }
        unexpected = written - allowed
        assert not unexpected, f"unexpected files written: {unexpected}"

    def test_all_packages_status_proposed_never_enforced(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_wave_schedule(td)
        from core.audit.operator_decision_assist import build_decision_assist_report
        report = build_decision_assist_report(td)
        for pkg in report["packages"]:
            assert pkg["status"] == "PROPOSED", (
                f"package {pkg['decision_id']} has status {pkg['status']!r} — must be PROPOSED"
            )
