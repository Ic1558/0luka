"""AG-39: Supervised Repair Wave Scheduler — test suite.

Tests:
  A. Wave Policy Unit Tests
  B. Scheduler Unit Tests
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


def _write_priority_queue(td: str, items: list[dict]) -> None:
    path = Path(td) / "state" / "repair_priority_queue.json"
    path.write_text(json.dumps({"ts": "2026-03-16T00:00:00Z", "total": len(items), "queue": items}))


def _write_stability(td: str, classification: str, score: int = 80) -> None:
    path = Path(td) / "state" / "runtime_stability_score.json"
    path.write_text(json.dumps({"score": score, "classification": classification}))


def _p1_item(fid: str = "f-p1", component: str = "core.x") -> dict:
    return {
        "finding_id": fid,
        "priority_score": 90,
        "priority_class": "P1",
        "component": component,
        "plan_id": "",
        "drift_type": "operator_gate_regression",
        "severity": "CRITICAL",
        "gov_status": "ESCALATED",
        "reasons": ["operator_gate_risk"],
        "recommended_order": 1,
    }


def _p2_item(fid: str = "f-p2", component: str = "core.y") -> dict:
    return {
        "finding_id": fid,
        "priority_score": 72,
        "priority_class": "P2",
        "component": component,
        "plan_id": "",
        "drift_type": "wiring_gap",
        "severity": "MEDIUM",
        "gov_status": "ESCALATED",
        "reasons": [],
        "recommended_order": 2,
    }


def _p4_item(fid: str = "f-p4", component: str = "core.z") -> dict:
    return {
        "finding_id": fid,
        "priority_score": 20,
        "priority_class": "P4",
        "component": component,
        "plan_id": "",
        "drift_type": "naming_drift",
        "severity": "LOW",
        "gov_status": "OPEN",
        "reasons": [],
        "recommended_order": 3,
    }


def _mock_request(body: dict) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Wave Policy Unit Tests
# ---------------------------------------------------------------------------

class TestWavePolicy:

    def test_default_policy_keys_present(self):
        from core.audit.wave_policy import DEFAULT_WAVE_POLICY
        p = DEFAULT_WAVE_POLICY
        assert "max_items_per_wave" in p
        assert "allow_target_overlap" in p
        assert "unstable_runtime_max_items" in p
        assert "degraded_runtime_max_items" in p
        assert p["allow_target_overlap"] is False

    def test_max_wave_size_stable(self):
        from core.audit.wave_policy import max_wave_size_for_stability
        assert max_wave_size_for_stability("STABLE") == 3

    def test_max_wave_size_degraded(self):
        from core.audit.wave_policy import max_wave_size_for_stability
        assert max_wave_size_for_stability("DEGRADED") == 2

    def test_max_wave_size_unstable(self):
        from core.audit.wave_policy import max_wave_size_for_stability
        assert max_wave_size_for_stability("UNSTABLE") == 1

    def test_max_wave_size_governance_risk(self):
        from core.audit.wave_policy import max_wave_size_for_stability
        assert max_wave_size_for_stability("GOVERNANCE_RISK") == 1

    def test_can_items_share_wave_different_components(self):
        from core.audit.wave_policy import can_items_share_wave
        a = {"component": "core.x", "plan_id": ""}
        b = {"component": "core.y", "plan_id": ""}
        assert can_items_share_wave(a, b) is True

    def test_can_items_share_wave_same_component_blocked(self):
        from core.audit.wave_policy import can_items_share_wave
        a = {"component": "core.x", "plan_id": ""}
        b = {"component": "core.x", "plan_id": ""}
        assert can_items_share_wave(a, b) is False

    def test_can_items_share_wave_same_plan_blocked(self):
        from core.audit.wave_policy import can_items_share_wave
        a = {"component": "core.x", "plan_id": "plan-001"}
        b = {"component": "core.y", "plan_id": "plan-001"}
        assert can_items_share_wave(a, b) is False

    def test_priority_bucket_order_p1_first(self):
        from core.audit.wave_policy import classify_wave_priority_bucket
        assert classify_wave_priority_bucket("P1") < classify_wave_priority_bucket("P2")
        assert classify_wave_priority_bucket("P2") < classify_wave_priority_bucket("P3")
        assert classify_wave_priority_bucket("P3") < classify_wave_priority_bucket("P4")

    def test_wave_eligibility_verdicts_defined(self):
        from core.audit.wave_policy import WAVE_ELIGIBILITY_VERDICTS
        assert set(WAVE_ELIGIBILITY_VERDICTS.keys()) == {"ELIGIBLE", "DEFER", "BLOCK", "ESCALATE"}

    def test_wave_states_defined(self):
        from core.audit.wave_policy import WAVE_STATES
        assert "PROPOSED" in WAVE_STATES
        assert "APPROVED" in WAVE_STATES
        assert "REJECTED" in WAVE_STATES
        assert "READY_FOR_EXECUTION" in WAVE_STATES


# ---------------------------------------------------------------------------
# Suite B: Scheduler Unit Tests
# ---------------------------------------------------------------------------

class TestSchedulerUnit:

    def test_classify_eligibility_eligible(self):
        from core.audit.repair_wave_scheduler import classify_wave_eligibility
        item = _p1_item()
        result = classify_wave_eligibility(item, [])
        assert result["verdict"] == "ELIGIBLE"

    def test_classify_eligibility_missing_finding_id_blocked(self):
        from core.audit.repair_wave_scheduler import classify_wave_eligibility
        item = {"finding_id": "", "priority_class": "P1", "component": "x"}
        result = classify_wave_eligibility(item, [])
        assert result["verdict"] == "BLOCK"

    def test_classify_eligibility_unknown_class_escalated(self):
        from core.audit.repair_wave_scheduler import classify_wave_eligibility
        item = {"finding_id": "f1", "priority_class": "PX", "component": "x"}
        result = classify_wave_eligibility(item, [])
        assert result["verdict"] == "ESCALATE"

    def test_classify_eligibility_overlap_blocked(self):
        from core.audit.repair_wave_scheduler import classify_wave_eligibility
        a = _p1_item("f1", "core.x")
        b = _p1_item("f2", "core.x")  # same component
        result = classify_wave_eligibility(b, [a])
        assert result["verdict"] == "BLOCK"

    def test_build_waves_p1_in_first_wave(self):
        from core.audit.repair_wave_scheduler import build_repair_waves
        items = [_p4_item("f-low"), _p1_item("f-high"), _p2_item("f-mid")]
        waves, _ = build_repair_waves(items)
        assert len(waves) >= 1
        first_wave_ids = {i["finding_id"] for i in waves[0]["items"]}
        assert "f-high" in first_wave_ids

    def test_build_waves_respects_max_items(self):
        from core.audit.repair_wave_scheduler import build_repair_waves
        from core.audit.wave_policy import DEFAULT_WAVE_POLICY
        items = [_p1_item(f"f{i}", f"comp.{i}") for i in range(6)]
        waves, deferred = build_repair_waves(items)
        for wave in waves:
            assert wave["item_count"] <= DEFAULT_WAVE_POLICY["max_items_per_wave"]

    def test_build_waves_unstable_reduces_size(self):
        from core.audit.repair_wave_scheduler import build_repair_waves
        items = [_p1_item(f"f{i}", f"comp.{i}") for i in range(4)]
        waves, _ = build_repair_waves(items, stability_classification="UNSTABLE")
        for wave in waves:
            assert wave["item_count"] <= 1

    def test_build_waves_no_overlap_within_wave(self):
        from core.audit.repair_wave_scheduler import build_repair_waves
        # Two items with same component — they must end up in different waves
        a = _p1_item("f1", "core.shared")
        b = _p1_item("f2", "core.shared")
        waves, _ = build_repair_waves([a, b])
        # Verify no wave contains both
        for wave in waves:
            fids = [i["finding_id"] for i in wave["items"]]
            assert not ("f1" in fids and "f2" in fids)

    def test_build_waves_all_proposed(self):
        from core.audit.repair_wave_scheduler import build_repair_waves
        items = [_p1_item(), _p2_item()]
        waves, _ = build_repair_waves(items)
        for wave in waves:
            assert wave["status"] == "PROPOSED"
            assert wave["operator_action_required"] is True

    def test_store_wave_schedule_writes_three_files(self):
        td = _make_tmpdir()
        from core.audit.repair_wave_scheduler import store_wave_schedule
        waves = [{"wave_id": "w1", "wave_number": 1, "status": "PROPOSED",
                  "items": [], "item_count": 0, "priority_classes_present": [],
                  "ts_created": "2026-03-16T00:00:00Z", "operator_action_required": True}]
        summary = {"ts": "2026-03-16T00:00:00Z", "total_waves": 1}
        store_wave_schedule(waves, [], summary, td)
        state = Path(td) / "state"
        assert (state / "repair_wave_schedule.json").exists()
        assert (state / "repair_wave_log.jsonl").exists()
        assert (state / "repair_wave_latest.json").exists()

    def test_approve_wave_transitions_status(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item()])
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling, approve_repair_wave
        result = run_repair_wave_scheduling(td)
        wave_id = result["first_wave_id"]
        approve_result = approve_repair_wave(wave_id, "boss", td)
        assert approve_result["ok"] is True
        assert approve_result["new_status"] == "APPROVED"

    def test_reject_wave_transitions_status(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item()])
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling, reject_repair_wave
        result = run_repair_wave_scheduling(td)
        wave_id = result["first_wave_id"]
        reject_result = reject_repair_wave(wave_id, "boss", "too risky", td)
        assert reject_result["ok"] is True
        assert reject_result["new_status"] == "REJECTED"

    def test_approve_non_proposed_fails(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item()])
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling, approve_repair_wave
        result = run_repair_wave_scheduling(td)
        wave_id = result["first_wave_id"]
        # Approve once
        approve_repair_wave(wave_id, "boss", td)
        # Try again — should fail
        second = approve_repair_wave(wave_id, "boss", td)
        assert second["ok"] is False

    def test_reject_non_proposed_fails(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item()])
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling, approve_repair_wave, reject_repair_wave
        result = run_repair_wave_scheduling(td)
        wave_id = result["first_wave_id"]
        approve_repair_wave(wave_id, "boss", td)
        # Now try to reject an APPROVED wave
        rej = reject_repair_wave(wave_id, "boss", "changed mind", td)
        assert rej["ok"] is False


# ---------------------------------------------------------------------------
# Suite C: Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_run_wave_scheduling_generates_waves(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item(), _p2_item()])
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling
        result = run_repair_wave_scheduling(td)
        assert result["ok"] is True
        assert result["total_waves"] >= 1

    def test_run_empty_queue_returns_zero_waves(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [])
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling
        result = run_repair_wave_scheduling(td)
        assert result["ok"] is True
        assert result["total_waves"] == 0
        assert result["first_wave_id"] is None

    def test_run_generates_all_three_output_files(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item()])
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling
        run_repair_wave_scheduling(td)
        state = Path(td) / "state"
        assert (state / "repair_wave_schedule.json").exists()
        assert (state / "repair_wave_log.jsonl").exists()
        assert (state / "repair_wave_latest.json").exists()

    def test_stability_affects_wave_size(self):
        td1 = _make_tmpdir()
        items = [_p1_item(f"f{i}", f"comp.{i}") for i in range(4)]
        _write_priority_queue(td1, items)
        _write_stability(td1, "STABLE")

        td2 = _make_tmpdir()
        _write_priority_queue(td2, items)
        _write_stability(td2, "GOVERNANCE_RISK", score=0)

        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling
        r1 = run_repair_wave_scheduling(td1)
        r2 = run_repair_wave_scheduling(td2)
        # GOVERNANCE_RISK → smaller waves → more waves needed for same items
        assert r2["total_waves"] >= r1["total_waves"]

    def test_api_wave_schedule_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_wave import repair_wave_schedule
        result = asyncio.run(repair_wave_schedule())
        assert result["ok"] is True
        assert "waves" in result

    def test_api_wave_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_wave import repair_wave_latest
        result = asyncio.run(repair_wave_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_wave_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_wave import repair_wave_run
        req = _mock_request({})
        resp = asyncio.run(repair_wave_run(req))
        assert resp.status_code == 403

    def test_api_wave_approve_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_wave import repair_wave_approve
        req = _mock_request({})
        resp = asyncio.run(repair_wave_approve("wave-fake", req))
        assert resp.status_code == 403

    def test_api_wave_reject_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_wave import repair_wave_reject
        req = _mock_request({})
        resp = asyncio.run(repair_wave_reject("wave-fake", req))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_wave_scheduling_does_not_execute_repairs(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item()])
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling
        run_repair_wave_scheduling(td)
        state = Path(td) / "state"
        assert not (state / "drift_repair_execution_log.jsonl").exists()

    def test_wave_scheduling_does_not_mutate_governance_state(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item()])
        # Write a governance file to confirm it's not touched
        gov_path = Path(td) / "state" / "drift_finding_status.json"
        gov_path.write_text(json.dumps({"f-p1": {"status": "ESCALATED"}}))
        mtime_before = gov_path.stat().st_mtime
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling
        run_repair_wave_scheduling(td)
        mtime_after = gov_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_wave_scheduling_does_not_modify_baseline(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item()])
        baseline_path = Path(__file__).parent.parent / "audit" / "audit_baseline.py"
        mtime_before = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling
        run_repair_wave_scheduling(td)
        mtime_after = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        assert mtime_before == mtime_after

    def test_outputs_limited_to_ag39_files(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item()])
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling
        run_repair_wave_scheduling(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        allowed = {
            "repair_priority_queue.json",
            "repair_wave_schedule.json",
            "repair_wave_log.jsonl",
            "repair_wave_latest.json",
        }
        unexpected = written - allowed
        assert not unexpected, f"unexpected files written: {unexpected}"

    def test_all_proposed_waves_require_operator_action(self):
        td = _make_tmpdir()
        _write_priority_queue(td, [_p1_item(), _p2_item("f2", "comp.b")])
        from core.audit.repair_wave_scheduler import run_repair_wave_scheduling, load_existing_wave_schedule
        run_repair_wave_scheduling(td)
        schedule = load_existing_wave_schedule(td)
        for wave in schedule.get("waves", []):
            if wave["status"] == "PROPOSED":
                assert wave["operator_action_required"] is True
