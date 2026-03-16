"""AG-35: Repair Verification & Governance Reconciliation — test suite.

Tests:
  A. Reconciliation Store
  B. Evidence Verification
  C. Drift Re-Check
  D. Governance Recommendation
  E. End-to-End Integration
  F. Safety Invariants
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


def _execution_record(**kwargs) -> dict[str, Any]:
    base = {
        "execution_id": "repair-exec-test01",
        "plan_id": "plan-test-001",
        "finding_id": "finding-test-001",
        "operator_id": "boss",
        "target_files": ["core/audit/test_dummy.py"],
        "before_state": [{"path": "core/audit/test_dummy.py", "sha256_before": "aaa", "exists_before": True}],
        "after_state": [{"path": "core/audit/test_dummy.py", "sha256_after": "bbb", "exists_after": True}],
        "executed_actions": ["add import statement", "add integration test"],
        "execution_model": "dry_record",
        "verification_status": "PASSED",
        "status": "EXECUTED",
        "scope_verdict": "ALLOW",
    }
    base.update(kwargs)
    return base


def _write_execution_record(td: str, record: dict) -> None:
    log_path = Path(td) / "state" / "drift_repair_execution_log.jsonl"
    with log_path.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def _mock_request(body: dict[str, Any]) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Reconciliation Store
# ---------------------------------------------------------------------------

class TestReconciliationStore:

    def test_append_and_list_records(self):
        td = _make_tmpdir()
        from core.audit.reconciliation_store import append_reconciliation_log, list_reconciliation_records
        record = {"reconciliation_id": "recon-001", "status": "RECONCILED"}
        append_reconciliation_log(record, td)
        records = list_reconciliation_records(td)
        assert len(records) == 1
        assert records[0]["reconciliation_id"] == "recon-001"

    def test_get_record_by_id(self):
        td = _make_tmpdir()
        from core.audit.reconciliation_store import append_reconciliation_log, get_reconciliation_record
        record = {"reconciliation_id": "recon-002"}
        append_reconciliation_log(record, td)
        found = get_reconciliation_record("recon-002", td)
        assert found is not None

    def test_get_record_missing_returns_none(self):
        td = _make_tmpdir()
        from core.audit.reconciliation_store import get_reconciliation_record
        assert get_reconciliation_record("nonexistent", td) is None

    def test_save_and_load_latest(self):
        td = _make_tmpdir()
        from core.audit.reconciliation_store import save_reconciliation_latest, load_reconciliation_latest
        summary = {"last_reconciliation_id": "recon-001", "drift_state": "DRIFT_CLEARED"}
        save_reconciliation_latest(summary, td)
        loaded = load_reconciliation_latest(td)
        assert loaded["drift_state"] == "DRIFT_CLEARED"

    def test_load_latest_empty_returns_empty_dict(self):
        td = _make_tmpdir()
        from core.audit.reconciliation_store import load_reconciliation_latest
        assert load_reconciliation_latest(td) == {}

    def test_log_is_append_only(self):
        td = _make_tmpdir()
        from core.audit.reconciliation_store import append_reconciliation_log, list_reconciliation_records
        append_reconciliation_log({"reconciliation_id": "a"}, td)
        append_reconciliation_log({"reconciliation_id": "b"}, td)
        records = list_reconciliation_records(td)
        assert len(records) == 2

    def test_new_reconciliation_id_is_unique(self):
        from core.audit.reconciliation_store import new_reconciliation_id
        ids = {new_reconciliation_id() for _ in range(20)}
        assert len(ids) == 20

    def test_missing_runtime_root_raises(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        import importlib
        from core.audit import reconciliation_store as rs
        importlib.reload(rs)
        with pytest.raises(RuntimeError, match="LUKA_RUNTIME_ROOT"):
            rs.append_reconciliation_log({"x": 1})


# ---------------------------------------------------------------------------
# Suite B: Evidence Verification
# ---------------------------------------------------------------------------

class TestEvidenceVerification:

    def test_passed_for_complete_executed_record(self):
        from core.audit.repair_reconciliation import verify_execution_evidence
        rec = _execution_record()
        result = verify_execution_evidence(rec)
        assert result["verification_status"] == "PASSED"

    def test_failed_for_no_executed_actions(self):
        from core.audit.repair_reconciliation import verify_execution_evidence
        rec = _execution_record(executed_actions=[])
        result = verify_execution_evidence(rec)
        assert result["verification_status"] == "FAILED"

    def test_failed_for_blocked_scope(self):
        from core.audit.repair_reconciliation import verify_execution_evidence
        rec = _execution_record(scope_verdict="BLOCK", status="FAILED")
        result = verify_execution_evidence(rec)
        assert result["verification_status"] == "FAILED"

    def test_inconclusive_for_missing_before_state(self):
        from core.audit.repair_reconciliation import verify_execution_evidence
        rec = _execution_record(before_state=[])
        result = verify_execution_evidence(rec)
        assert result["verification_status"] in ("INCONCLUSIVE", "FAILED")

    def test_inconclusive_for_missing_after_state(self):
        from core.audit.repair_reconciliation import verify_execution_evidence
        rec = _execution_record(after_state=[])
        result = verify_execution_evidence(rec)
        assert result["verification_status"] in ("INCONCLUSIVE", "FAILED")

    def test_checks_list_is_always_present(self):
        from core.audit.repair_reconciliation import verify_execution_evidence
        rec = _execution_record()
        result = verify_execution_evidence(rec)
        assert isinstance(result["checks"], list)
        assert len(result["checks"]) > 0

    def test_reason_is_always_present(self):
        from core.audit.repair_reconciliation import verify_execution_evidence
        rec = _execution_record()
        result = verify_execution_evidence(rec)
        assert "reason" in result
        assert len(result["reason"]) > 0


# ---------------------------------------------------------------------------
# Suite C: Drift Re-Check
# ---------------------------------------------------------------------------

class TestDriftReCheck:

    def test_drift_inconclusive_for_dry_record_model(self):
        from core.audit.repair_reconciliation import bounded_drift_recheck
        # dry_record model: hashes won't differ — should be INCONCLUSIVE not DRIFT_PERSISTS
        rec = _execution_record()  # execution_model=dry_record, sha256_before != sha256_after
        # But execution model is dry_record so same hashes → INCONCLUSIVE
        rec2 = _execution_record(
            before_state=[{"path": "f.py", "sha256_before": "abc"}],
            after_state=[{"path": "f.py", "sha256_after": "abc"}],  # unchanged
            execution_model="dry_record",
        )
        result = bounded_drift_recheck(rec2)
        assert result == "DRIFT_INCONCLUSIVE"

    def test_drift_cleared_when_hash_changed(self):
        from core.audit.repair_reconciliation import bounded_drift_recheck
        rec = _execution_record(execution_model="live")  # non-dry
        # before != after → DRIFT_CLEARED
        result = bounded_drift_recheck(rec)
        assert result == "DRIFT_CLEARED"

    def test_drift_persists_when_no_change_not_dry(self):
        from core.audit.repair_reconciliation import bounded_drift_recheck
        rec = _execution_record(
            before_state=[{"path": "f.py", "sha256_before": "same"}],
            after_state=[{"path": "f.py", "sha256_after": "same"}],
            execution_model="live",
        )
        result = bounded_drift_recheck(rec)
        assert result == "DRIFT_PERSISTS"

    def test_drift_regressed_when_file_missing_after(self):
        from core.audit.repair_reconciliation import bounded_drift_recheck
        rec = _execution_record(
            before_state=[{"path": "f.py", "sha256_before": "abc"}],
            after_state=[],  # file gone
            execution_model="live",
        )
        # Missing after_state → INCONCLUSIVE (no snapshots)
        result = bounded_drift_recheck(rec)
        assert result in ("DRIFT_INCONCLUSIVE", "DRIFT_REGRESSED")

    def test_drift_inconclusive_when_no_state_snapshots(self):
        from core.audit.repair_reconciliation import bounded_drift_recheck
        rec = _execution_record(before_state=[], after_state=[])
        result = bounded_drift_recheck(rec)
        assert result == "DRIFT_INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Suite D: Governance Recommendation
# ---------------------------------------------------------------------------

class TestGovernanceRecommendation:

    def test_recommend_resolved_when_cleared_and_passed(self):
        from core.audit.repair_reconciliation import compute_governance_recommendation
        assert compute_governance_recommendation("DRIFT_CLEARED", "PASSED") == "recommend_RESOLVED"

    def test_recommend_open_when_cleared_inconclusive(self):
        from core.audit.repair_reconciliation import compute_governance_recommendation
        assert compute_governance_recommendation("DRIFT_CLEARED", "INCONCLUSIVE") == "recommend_OPEN"

    def test_recommend_escalated_when_persists(self):
        from core.audit.repair_reconciliation import compute_governance_recommendation
        for v in ("PASSED", "FAILED", "INCONCLUSIVE"):
            assert compute_governance_recommendation("DRIFT_PERSISTS", v) == "recommend_ESCALATED_AGAIN"

    def test_recommend_high_priority_when_regressed(self):
        from core.audit.repair_reconciliation import compute_governance_recommendation
        for v in ("PASSED", "FAILED", "INCONCLUSIVE"):
            assert compute_governance_recommendation("DRIFT_REGRESSED", v) == "recommend_HIGH_PRIORITY_ESCALATION"

    def test_all_drift_states_produce_recommendation(self):
        from core.audit.repair_reconciliation import compute_governance_recommendation
        for ds in ("DRIFT_CLEARED", "DRIFT_PERSISTS", "DRIFT_REGRESSED", "DRIFT_INCONCLUSIVE"):
            for vs in ("PASSED", "FAILED", "INCONCLUSIVE"):
                rec = compute_governance_recommendation(ds, vs)
                assert rec.startswith("recommend_"), f"bad recommendation for ({ds},{vs}): {rec}"


# ---------------------------------------------------------------------------
# Suite E: End-to-End Integration
# ---------------------------------------------------------------------------

class TestEndToEndIntegration:

    def test_run_reconciliation_creates_log_entry(self):
        td = _make_tmpdir()
        _write_execution_record(td, _execution_record())
        from core.audit.repair_reconciliation import run_reconciliation
        from core.audit.reconciliation_store import list_reconciliation_records
        result = run_reconciliation("repair-exec-test01", "boss", td)
        assert result["ok"] is True
        records = list_reconciliation_records(td)
        assert len(records) == 1

    def test_run_reconciliation_writes_latest_summary(self):
        td = _make_tmpdir()
        _write_execution_record(td, _execution_record())
        from core.audit.repair_reconciliation import run_reconciliation
        from core.audit.reconciliation_store import load_reconciliation_latest
        run_reconciliation("repair-exec-test01", "boss", td)
        latest = load_reconciliation_latest(td)
        assert latest.get("execution_id") == "repair-exec-test01"
        assert latest.get("operator_action_required") is True

    def test_run_reconciliation_not_found_returns_failed(self):
        td = _make_tmpdir()
        from core.audit.repair_reconciliation import run_reconciliation
        result = run_reconciliation("nonexistent-exec", "boss", td)
        assert result["ok"] is False
        assert result["status"] == "FAILED"

    def test_run_reconciliation_returns_governance_recommendation(self):
        td = _make_tmpdir()
        _write_execution_record(td, _execution_record())
        from core.audit.repair_reconciliation import run_reconciliation
        result = run_reconciliation("repair-exec-test01", "boss", td)
        assert "governance_recommendation" in result
        assert result["governance_recommendation"].startswith("recommend_")

    def test_api_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_reconciliation import repair_reconciliation_run
        req = _mock_request({"execution_id": "exec-001"})
        resp = asyncio.run(repair_reconciliation_run(req))
        assert resp.status_code == 403

    def test_api_run_requires_execution_id(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_reconciliation import repair_reconciliation_run
        req = _mock_request({"operator_id": "boss"})
        resp = asyncio.run(repair_reconciliation_run(req))
        assert resp.status_code == 400

    def test_api_history_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_reconciliation import repair_reconciliation_history
        result = asyncio.run(repair_reconciliation_history())
        assert result["ok"] is True
        assert "records" in result

    def test_api_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_reconciliation import repair_reconciliation_latest
        result = asyncio.run(repair_reconciliation_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_by_id_not_found(self):
        td = _make_tmpdir()
        from interface.operator.api_repair_reconciliation import repair_reconciliation_by_id
        result = asyncio.run(repair_reconciliation_by_id("nonexistent"))
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Suite F: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def test_reconciliation_does_not_modify_audit_baseline(self):
        td = _make_tmpdir()
        baseline_path = Path(__file__).parent.parent / "audit" / "audit_baseline.py"
        mtime_before = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        _write_execution_record(td, _execution_record())
        from core.audit.repair_reconciliation import run_reconciliation
        run_reconciliation("repair-exec-test01", "boss", td)
        mtime_after = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        assert mtime_before == mtime_after

    def test_reconciliation_does_not_modify_finding_status(self):
        td = _make_tmpdir()
        state = Path(td) / "state"
        status_path = state / "drift_finding_status.json"
        status_path.write_text(json.dumps({"finding-test-001": {"status": "ESCALATED"}}))
        mtime_before = status_path.stat().st_mtime
        _write_execution_record(td, _execution_record())
        from core.audit.repair_reconciliation import run_reconciliation
        run_reconciliation("repair-exec-test01", "boss", td)
        mtime_after = status_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_reconciliation_does_not_modify_governance_log(self):
        td = _make_tmpdir()
        state = Path(td) / "state"
        log_path = state / "drift_governance_log.jsonl"
        log_path.write_text('{"action": "existing"}\n')
        mtime_before = log_path.stat().st_mtime
        _write_execution_record(td, _execution_record())
        from core.audit.repair_reconciliation import run_reconciliation
        run_reconciliation("repair-exec-test01", "boss", td)
        mtime_after = log_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_reconciliation_operator_action_required_always_true(self):
        td = _make_tmpdir()
        _write_execution_record(td, _execution_record())
        from core.audit.repair_reconciliation import run_reconciliation
        from core.audit.reconciliation_store import list_reconciliation_records
        run_reconciliation("repair-exec-test01", "boss", td)
        records = list_reconciliation_records(td)
        assert all(r.get("operator_action_required") is True for r in records)

    def test_reconciliation_outputs_limited_to_reconciliation_files(self):
        td = _make_tmpdir()
        state = Path(td) / "state"
        _write_execution_record(td, _execution_record())
        from core.audit.repair_reconciliation import run_reconciliation
        run_reconciliation("repair-exec-test01", "boss", td)
        written = {f.name for f in state.iterdir()}
        allowed = {
            "drift_repair_execution_log.jsonl",
            "repair_reconciliation_log.jsonl",
            "repair_reconciliation_latest.json",
        }
        unexpected = written - allowed
        assert not unexpected, f"unexpected files written: {unexpected}"

    def test_reconciliation_status_is_reconciled(self):
        td = _make_tmpdir()
        _write_execution_record(td, _execution_record())
        from core.audit.reconciliation_store import list_reconciliation_records
        from core.audit.repair_reconciliation import run_reconciliation
        run_reconciliation("repair-exec-test01", "boss", td)
        records = list_reconciliation_records(td)
        assert records[0]["status"] == "RECONCILED"
