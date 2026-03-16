"""AG-44: Supervisory Decision Queue Governance — test suite.

Tests:
  A. Decision Queue Policy Unit Tests
  B. Decision Queue Governance Unit Tests
  C. Integration Tests
  D. Safety Invariants
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
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
    mode_path = Path(td) / "state" / "runtime_operating_mode.json"
    mode_path.write_text(json.dumps({"operating_mode": mode, "confidence": 0.82}))
    strategy_path = Path(td) / "state" / "runtime_strategy_latest.json"
    strategy_path.write_text(json.dumps({
        "operating_mode": mode,
        "key_risks": ["stability_degraded"],
        "recommendations": [],
    }))


def _write_decision_queue(td: str, packages: list | None = None) -> None:
    pkgs = packages or [
        {
            "decision_id": "decision-001",
            "decision_type": "APPROVE_REPAIR_WAVE",
            "target_ref": "wave-001",
            "priority": "HIGH",
            "status": "PROPOSED",
            "operating_mode": "CONSERVATIVE",
            "summary": "Approve wave for repair.",
            "rationale": "Wave is ready.",
            "risks": [],
            "alternatives": ["DEFER_REPAIR_WAVE"],
            "evidence_refs": ["repair_wave_schedule.json"],
            "recommended_action": "APPROVE",
            "operator_action_required": True,
            "ts": "2026-03-16T00:00:00Z",
        },
        {
            "decision_id": "decision-002",
            "decision_type": "PAUSE_NEW_CAMPAIGNS",
            "target_ref": "campaign-system",
            "priority": "CRITICAL",
            "status": "PROPOSED",
            "operating_mode": "STABILIZE",
            "summary": "Pause campaigns due to instability.",
            "rationale": "System in STABILIZE mode.",
            "risks": ["instability"],
            "alternatives": ["REQUIRE_GOVERNANCE_REVIEW"],
            "evidence_refs": ["runtime_strategy_latest.json"],
            "recommended_action": "PAUSE",
            "operator_action_required": True,
            "ts": "2026-03-16T00:00:00Z",
        },
    ]
    path = Path(td) / "state" / "operator_decision_queue.json"
    path.write_text(json.dumps({"packages": pkgs, "pending": len(pkgs), "operating_mode": "CONSERVATIVE"}))


def _mock_request(body: dict) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Decision Queue Policy Unit Tests
# ---------------------------------------------------------------------------

class TestDecisionQueuePolicy:

    def test_queue_priority_classes_defined(self):
        from core.audit.decision_queue_policy import QUEUE_PRIORITY_CLASSES
        assert set(QUEUE_PRIORITY_CLASSES.keys()) == {"Q1", "Q2", "Q3", "Q4"}

    def test_queue_statuses_defined(self):
        from core.audit.decision_queue_policy import QUEUE_STATUSES
        assert {"OPEN", "DEFERRED", "STALE", "SUPERSEDED", "ARCHIVED"}.issubset(QUEUE_STATUSES)

    def test_allowed_transitions_archived_is_terminal(self):
        from core.audit.decision_queue_policy import ALLOWED_TRANSITIONS
        assert ALLOWED_TRANSITIONS["ARCHIVED"] == set()

    def test_valid_queue_status_transition_open_to_deferred(self):
        from core.audit.decision_queue_policy import valid_queue_status_transition
        assert valid_queue_status_transition("OPEN", "DEFERRED") is True

    def test_valid_queue_status_transition_archived_to_open_blocked(self):
        from core.audit.decision_queue_policy import valid_queue_status_transition
        assert valid_queue_status_transition("ARCHIVED", "OPEN") is False

    def test_valid_queue_status_transition_superseded_to_archived(self):
        from core.audit.decision_queue_policy import valid_queue_status_transition
        assert valid_queue_status_transition("SUPERSEDED", "ARCHIVED") is True

    def test_classify_queue_priority_class_high_score_is_q1(self):
        from core.audit.decision_queue_policy import classify_queue_priority_class
        assert classify_queue_priority_class(85) == "Q1"

    def test_classify_queue_priority_class_low_score_is_q4(self):
        from core.audit.decision_queue_policy import classify_queue_priority_class
        assert classify_queue_priority_class(10) == "Q4"

    def test_classify_age_bucket_fresh(self):
        from core.audit.decision_queue_policy import classify_age_bucket
        ts = time.time() - 100  # 100 seconds old
        assert classify_age_bucket(ts) == "FRESH"

    def test_classify_age_bucket_stale(self):
        from core.audit.decision_queue_policy import classify_age_bucket
        ts = time.time() - (86400 * 4)  # 4 days old
        assert classify_age_bucket(ts) == "STALE"

    def test_score_queue_entry_critical_priority_scores_high(self):
        from core.audit.decision_queue_policy import score_queue_entry
        pkg = {
            "decision_type": "PAUSE_NEW_CAMPAIGNS",
            "priority": "CRITICAL",
            "ts": time.time() - 100,
        }
        score = score_queue_entry(pkg, "STABILIZE")
        assert score >= 80  # Q1 territory

    def test_queue_priority_rank_q1_is_lower_than_q4(self):
        from core.audit.decision_queue_policy import queue_priority_rank
        assert queue_priority_rank("Q1") < queue_priority_rank("Q4")


# ---------------------------------------------------------------------------
# Suite B: Decision Queue Governance Unit Tests
# ---------------------------------------------------------------------------

class TestDecisionQueueGovernance:

    def test_load_decision_packages_returns_list(self):
        td = _make_tmpdir()
        _write_decision_queue(td)
        from core.audit.decision_queue_governance import load_decision_packages
        pkgs = load_decision_packages(td)
        assert isinstance(pkgs, list)
        assert len(pkgs) == 2

    def test_load_decision_packages_empty_on_missing_file(self):
        td = _make_tmpdir()
        from core.audit.decision_queue_governance import load_decision_packages
        pkgs = load_decision_packages(td)
        assert pkgs == []

    def test_classify_queue_priority_returns_class(self):
        td = _make_tmpdir()
        _write_strategy(td, "STABILIZE")
        from core.audit.decision_queue_governance import classify_queue_priority
        pkg = {
            "decision_type": "PAUSE_NEW_CAMPAIGNS",
            "priority": "CRITICAL",
            "ts": time.time() - 100,
        }
        cls = classify_queue_priority(pkg, "STABILIZE")
        assert cls in {"Q1", "Q2", "Q3", "Q4"}

    def test_build_decision_queue_sorted_by_priority(self):
        td = _make_tmpdir()
        _write_decision_queue(td)
        from core.audit.decision_queue_governance import (
            load_decision_packages, build_decision_queue,
        )
        pkgs = load_decision_packages(td)
        queue = build_decision_queue(pkgs, {}, "STABILIZE")
        ranks = [e["queue_priority_rank"] for e in queue]
        assert ranks == sorted(ranks)

    def test_defer_decision_transitions_to_deferred(self):
        td = _make_tmpdir()
        from core.audit.decision_queue_governance import defer_decision
        result = defer_decision("decision-001", "boss", "test deferral", td)
        assert result["ok"] is True
        assert result["new_status"] == "DEFERRED"

    def test_reopen_decision_transitions_deferred_to_open(self):
        td = _make_tmpdir()
        from core.audit.decision_queue_governance import defer_decision, reopen_decision
        defer_decision("decision-001", "boss", "", td)
        result = reopen_decision("decision-001", "boss", "", td)
        assert result["ok"] is True
        assert result["new_status"] == "OPEN"

    def test_supersede_decision_transitions_to_superseded(self):
        td = _make_tmpdir()
        from core.audit.decision_queue_governance import supersede_decision
        result = supersede_decision("decision-001", "boss", "decision-002", td)
        assert result["ok"] is True
        assert result["new_status"] == "SUPERSEDED"

    def test_archive_decision_terminal(self):
        td = _make_tmpdir()
        from core.audit.decision_queue_governance import archive_decision
        result = archive_decision("decision-001", "boss", "cleanup", td)
        assert result["ok"] is True
        assert result["new_status"] == "ARCHIVED"

    def test_archive_from_archived_blocked(self):
        td = _make_tmpdir()
        from core.audit.decision_queue_governance import archive_decision
        archive_decision("decision-001", "boss", "", td)
        result = archive_decision("decision-001", "boss", "", td)
        assert result["ok"] is False

    def test_expire_stale_decisions_marks_stale(self):
        td = _make_tmpdir()
        # Package with ts 4 days ago — should expire
        old_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 86400 * 4))
        pkgs = [{
            "decision_id": "decision-old",
            "decision_type": "APPROVE_REPAIR_WAVE",
            "priority": "HIGH",
            "status": "OPEN",
            "ts": old_ts,
            "operator_action_required": True,
        }]
        from core.audit.decision_queue_governance import (
            build_decision_queue, expire_stale_decisions,
        )
        queue = build_decision_queue(pkgs, {}, "CONSERVATIVE")
        updated, stale_count = expire_stale_decisions(queue, {}, td)
        assert stale_count == 1
        assert updated[0]["status"] == "STALE"

    def test_build_decision_queue_report_contains_required_fields(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_decision_queue(td)
        from core.audit.decision_queue_governance import build_decision_queue_report
        report = build_decision_queue_report(td)
        required = {"ts", "run_id", "operating_mode", "total_packages", "open_count",
                    "deferred_count", "stale_count", "urgent_count", "queue",
                    "type_distribution", "top_decision", "operator_action_required"}
        assert required.issubset(set(report.keys()))
        assert report["operator_action_required"] is True

    def test_store_decision_queue_writes_three_outputs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_decision_queue(td)
        from core.audit.decision_queue_governance import build_decision_queue_report, store_decision_queue
        report = build_decision_queue_report(td)
        store_decision_queue(report, td)
        state = Path(td) / "state"
        assert (state / "decision_queue_governance_log.jsonl").exists()
        assert (state / "decision_queue_governance_latest.json").exists()
        assert (state / "decision_queue_summary.json").exists()


# ---------------------------------------------------------------------------
# Suite C: Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_run_decision_queue_governance_returns_ok(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_decision_queue(td)
        from core.audit.decision_queue_governance import run_decision_queue_governance
        result = run_decision_queue_governance(td)
        assert result["ok"] is True
        assert result["operating_mode"] is not None

    def test_run_generates_all_three_output_files(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_decision_queue(td)
        from core.audit.decision_queue_governance import run_decision_queue_governance
        run_decision_queue_governance(td)
        state = Path(td) / "state"
        assert (state / "decision_queue_governance_log.jsonl").exists()
        assert (state / "decision_queue_governance_latest.json").exists()
        assert (state / "decision_queue_summary.json").exists()

    def test_run_no_inputs_defaults_gracefully(self):
        td = _make_tmpdir()
        from core.audit.decision_queue_governance import run_decision_queue_governance
        result = run_decision_queue_governance(td)
        assert result["ok"] is True

    def test_api_decision_queue_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_queue import decision_queue_latest
        result = asyncio.run(decision_queue_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_decision_queue_summary_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_queue import decision_queue_summary
        result = asyncio.run(decision_queue_summary())
        assert result["ok"] is True
        assert "open_count" in result

    def test_api_decision_queue_state_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_queue import decision_queue_state
        result = asyncio.run(decision_queue_state())
        assert result["ok"] is True
        assert "entries" in result

    def test_api_decision_queue_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_queue import decision_queue_run
        req = _mock_request({})
        resp = asyncio.run(decision_queue_run(req))
        assert resp.status_code == 403

    def test_api_decision_queue_run_generates_outputs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_decision_queue(td)
        from interface.operator.api_decision_queue import decision_queue_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(decision_queue_run(req))
        data = json.loads(resp.body)
        assert data["ok"] is True
        assert data["operating_mode"] is not None

    def test_api_defer_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_queue import decision_queue_defer
        req = _mock_request({"decision_id": "decision-001"})
        resp = asyncio.run(decision_queue_defer(req))
        assert resp.status_code == 403

    def test_api_defer_succeeds_with_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_queue import decision_queue_defer
        req = _mock_request({"operator_id": "boss", "decision_id": "decision-001"})
        resp = asyncio.run(decision_queue_defer(req))
        data = json.loads(resp.body)
        assert data["ok"] is True
        assert data["new_status"] == "DEFERRED"

    def test_api_archive_requires_decision_id(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_queue import decision_queue_archive
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(decision_queue_archive(req))
        assert resp.status_code == 400

    def test_api_by_id_not_found(self):
        td = _make_tmpdir()
        from interface.operator.api_decision_queue import decision_queue_by_id
        result = asyncio.run(decision_queue_by_id("decision-nonexistent"))
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Suite D: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_queue_governance_does_not_mutate_governance_state(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_decision_queue(td)
        gov_path = Path(td) / "state" / "drift_finding_status.json"
        gov_path.write_text(json.dumps({"f-001": {"status": "ESCALATED"}}))
        mtime_before = gov_path.stat().st_mtime
        from core.audit.decision_queue_governance import run_decision_queue_governance
        run_decision_queue_governance(td)
        assert gov_path.stat().st_mtime == mtime_before

    def test_queue_governance_does_not_execute_repairs(self):
        td = _make_tmpdir()
        _write_strategy(td)
        from core.audit.decision_queue_governance import run_decision_queue_governance
        run_decision_queue_governance(td)
        state = Path(td) / "state"
        assert not (state / "drift_repair_execution_log.jsonl").exists()

    def test_queue_governance_does_not_modify_ag43_packages(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_decision_queue(td)
        pkg_path = Path(td) / "state" / "operator_decision_queue.json"
        mtime_before = pkg_path.stat().st_mtime
        from core.audit.decision_queue_governance import run_decision_queue_governance
        run_decision_queue_governance(td)
        assert pkg_path.stat().st_mtime == mtime_before

    def test_outputs_limited_to_ag44_files(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_decision_queue(td)
        from core.audit.decision_queue_governance import run_decision_queue_governance
        run_decision_queue_governance(td)
        state = Path(td) / "state"
        written = {f.name for f in state.iterdir()}
        allowed = {
            # pre-existing inputs
            "runtime_operating_mode.json",
            "runtime_strategy_latest.json",
            "operator_decision_queue.json",
            # AG-44 outputs
            "decision_queue_governance_log.jsonl",
            "decision_queue_governance_latest.json",
            "decision_queue_summary.json",
            "decision_queue_state.json",
        }
        unexpected = written - allowed
        assert not unexpected, f"unexpected files written: {unexpected}"

    def test_operator_action_required_always_true(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_decision_queue(td)
        from core.audit.decision_queue_governance import build_decision_queue_report
        report = build_decision_queue_report(td)
        assert report["operator_action_required"] is True

    def test_deferred_decisions_do_not_auto_reopen(self):
        td = _make_tmpdir()
        _write_strategy(td)
        _write_decision_queue(td)
        from core.audit.decision_queue_governance import (
            defer_decision, run_decision_queue_governance, load_queue_state,
        )
        defer_decision("decision-001", "boss", "", td)
        run_decision_queue_governance(td)
        state = load_queue_state(td)
        # After a governance run, deferred decision must still be DEFERRED
        assert state.get("decision-001", {}).get("status") == "DEFERRED"
