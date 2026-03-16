"""AG-34: Supervised Drift Repair Execution — test suite.

Tests:
  A. Unit tests           — store, scope validation, state capture
  B. Integration tests    — end-to-end execution flow
  C. Safety tests         — no unapproved execution, no scope escape, no baseline mutation

41 tests across 6 suites.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tmpdir():
    td = tempfile.mkdtemp()
    os.environ["LUKA_RUNTIME_ROOT"] = td
    state = Path(td) / "state"
    state.mkdir(parents=True, exist_ok=True)
    return td


def _approved_plan(**kwargs) -> dict[str, Any]:
    base = {
        "plan_id": "plan-test-001",
        "finding_id": "finding-test-001",
        "operator_id": "boss",
        "approved_at": "2026-03-16T00:00:00Z",
        "approved_target_files": ["core/audit/test_dummy.py"],
        "approved_action_scope": "wire_component_into_runtime_path",
        "status": "APPROVED",
        "target_files": ["core/audit/test_dummy.py"],
        "proposed_actions": ["add import statement", "add integration test"],
        "drift_type": "wiring_gap",
        "repair_strategy": "wire_component_into_runtime_path",
    }
    base.update(kwargs)
    return base


def _proposed_plan(**kwargs) -> dict[str, Any]:
    plan = _approved_plan(**kwargs)
    plan["status"] = "PROPOSED"
    plan.pop("approved_at", None)
    plan.pop("approved_target_files", None)
    plan.pop("approved_action_scope", None)
    return plan


def _mock_request(body: dict[str, Any]) -> MagicMock:
    async def _json():
        return body
    req = MagicMock()
    req.json = _json
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": ""
    return req


# ---------------------------------------------------------------------------
# Suite A: Repair Execution Store
# ---------------------------------------------------------------------------

class TestRepairExecutionStore:

    def test_append_and_list_records(self):
        td = _make_tmpdir()
        from core.audit.repair_execution_store import append_repair_execution_log, list_execution_records
        record = {"execution_id": "exec-001", "status": "EXECUTED", "ts": "2026-03-16T00:00:00Z"}
        append_repair_execution_log(record, td)
        records = list_execution_records(td)
        assert len(records) == 1
        assert records[0]["execution_id"] == "exec-001"

    def test_get_execution_record_by_id(self):
        td = _make_tmpdir()
        from core.audit.repair_execution_store import append_repair_execution_log, get_execution_record
        record = {"execution_id": "exec-002", "status": "EXECUTED"}
        append_repair_execution_log(record, td)
        found = get_execution_record("exec-002", td)
        assert found is not None
        assert found["execution_id"] == "exec-002"

    def test_get_execution_record_missing_returns_none(self):
        td = _make_tmpdir()
        from core.audit.repair_execution_store import get_execution_record
        assert get_execution_record("nonexistent", td) is None

    def test_save_and_load_latest(self):
        td = _make_tmpdir()
        from core.audit.repair_execution_store import save_repair_execution_latest, load_repair_execution_latest
        summary = {"ts": "2026-03-16T00:00:00Z", "last_execution_id": "exec-001", "status": "EXECUTED"}
        save_repair_execution_latest(summary, td)
        loaded = load_repair_execution_latest(td)
        assert loaded["last_execution_id"] == "exec-001"

    def test_load_latest_empty_returns_empty_dict(self):
        td = _make_tmpdir()
        from core.audit.repair_execution_store import load_repair_execution_latest
        result = load_repair_execution_latest(td)
        assert result == {}

    def test_log_is_append_only(self):
        td = _make_tmpdir()
        from core.audit.repair_execution_store import append_repair_execution_log, list_execution_records
        append_repair_execution_log({"execution_id": "exec-a"}, td)
        append_repair_execution_log({"execution_id": "exec-b"}, td)
        records = list_execution_records(td)
        assert len(records) == 2

    def test_new_execution_id_is_unique(self):
        from core.audit.repair_execution_store import new_execution_id
        ids = {new_execution_id() for _ in range(20)}
        assert len(ids) == 20

    def test_missing_runtime_root_raises(self):
        os.environ.pop("LUKA_RUNTIME_ROOT", None)
        from core.audit import repair_execution_store as rs
        import importlib
        importlib.reload(rs)
        with pytest.raises(RuntimeError, match="LUKA_RUNTIME_ROOT"):
            rs.append_repair_execution_log({"x": 1})


# ---------------------------------------------------------------------------
# Suite B: Scope Validation
# ---------------------------------------------------------------------------

class TestScopeValidation:

    def test_allow_for_valid_approved_plan(self):
        from core.audit.drift_repair_executor import validate_execution_scope
        plan = _approved_plan()
        result = validate_execution_scope(plan)
        assert result["verdict"] == "ALLOW"

    def test_block_proposed_plan(self):
        from core.audit.drift_repair_executor import validate_execution_scope
        plan = _proposed_plan()
        result = validate_execution_scope(plan)
        assert result["verdict"] == "BLOCK"
        assert "APPROVED" in result["reason"]

    def test_block_missing_operator_id(self):
        from core.audit.drift_repair_executor import validate_execution_scope
        plan = _approved_plan(operator_id="")
        result = validate_execution_scope(plan)
        assert result["verdict"] == "BLOCK"
        assert "operator_id" in result["reason"]

    def test_block_missing_plan_id(self):
        from core.audit.drift_repair_executor import validate_execution_scope
        plan = _approved_plan(plan_id="")
        result = validate_execution_scope(plan)
        assert result["verdict"] == "BLOCK"

    def test_block_empty_target_files(self):
        from core.audit.drift_repair_executor import validate_execution_scope
        plan = _approved_plan(approved_target_files=[])
        result = validate_execution_scope(plan)
        assert result["verdict"] == "BLOCK"

    def test_block_audit_baseline_target(self):
        from core.audit.drift_repair_executor import validate_execution_scope
        plan = _approved_plan(approved_target_files=["core/audit/audit_baseline.py"])
        result = validate_execution_scope(plan)
        assert result["verdict"] == "BLOCK"
        assert "forbidden" in result["reason"]

    def test_block_env_file_target(self):
        from core.audit.drift_repair_executor import validate_execution_scope
        plan = _approved_plan(approved_target_files=[".env"])
        result = validate_execution_scope(plan)
        assert result["verdict"] == "BLOCK"

    def test_block_absolute_path_target(self):
        from core.audit.drift_repair_executor import validate_execution_scope
        plan = _approved_plan(approved_target_files=["/etc/passwd"])
        result = validate_execution_scope(plan)
        assert result["verdict"] == "BLOCK"

    def test_block_drift_governance_state_target(self):
        from core.audit.drift_repair_executor import validate_execution_scope
        plan = _approved_plan(approved_target_files=["drift_finding_status.json"])
        result = validate_execution_scope(plan)
        assert result["verdict"] == "BLOCK"

    def test_escalate_when_target_files_outside_approved(self):
        from core.audit.drift_repair_executor import validate_execution_scope
        plan = _approved_plan(
            approved_target_files=["core/audit/test_dummy.py"],
            target_files=["core/audit/test_dummy.py", "core/router.py"],
        )
        result = validate_execution_scope(plan)
        assert result["verdict"] == "ESCALATE"


# ---------------------------------------------------------------------------
# Suite C: State Capture
# ---------------------------------------------------------------------------

class TestStateCapture:

    def test_capture_pre_state_for_existing_file(self, tmp_path):
        td = str(tmp_path / "runtime")
        os.makedirs(td, exist_ok=True)
        os.environ["LUKA_RUNTIME_ROOT"] = td
        # Create a dummy file in the repo root (parent of runtime)
        dummy = tmp_path / "core" / "audit" / "test_dummy.py"
        dummy.parent.mkdir(parents=True, exist_ok=True)
        dummy.write_text("# test\n")

        from core.audit.drift_repair_executor import capture_pre_repair_state
        plan = _approved_plan()
        state = capture_pre_repair_state(plan, tmp_path)
        snaps = state["snapshots"]
        assert len(snaps) == 1
        assert snaps[0]["exists_before"] is True
        assert len(snaps[0]["sha256_before"]) == 64

    def test_capture_pre_state_for_missing_file(self, tmp_path):
        td = str(tmp_path / "runtime")
        os.makedirs(td, exist_ok=True)
        os.environ["LUKA_RUNTIME_ROOT"] = td

        from core.audit.drift_repair_executor import capture_pre_repair_state
        plan = _approved_plan()  # target file doesn't exist in tmp_path
        state = capture_pre_repair_state(plan, tmp_path)
        snaps = state["snapshots"]
        assert snaps[0]["exists_before"] is False
        assert snaps[0]["sha256_before"] == ""

    def test_capture_post_state_records_sha256(self, tmp_path):
        td = str(tmp_path / "runtime")
        os.makedirs(td, exist_ok=True)
        os.environ["LUKA_RUNTIME_ROOT"] = td
        dummy = tmp_path / "core" / "audit" / "test_dummy.py"
        dummy.parent.mkdir(parents=True, exist_ok=True)
        dummy.write_text("# modified\n")

        from core.audit.drift_repair_executor import capture_post_repair_state
        plan = _approved_plan()
        state = capture_post_repair_state(plan, tmp_path)
        snaps = state["snapshots"]
        assert snaps[0]["exists_after"] is True
        assert len(snaps[0]["sha256_after"]) == 64

    def test_pre_and_post_hashes_differ_after_file_change(self, tmp_path):
        td = str(tmp_path / "runtime")
        os.makedirs(td, exist_ok=True)
        os.environ["LUKA_RUNTIME_ROOT"] = td
        dummy = tmp_path / "core" / "audit" / "test_dummy.py"
        dummy.parent.mkdir(parents=True, exist_ok=True)
        dummy.write_text("# v1\n")

        from core.audit.drift_repair_executor import capture_pre_repair_state, capture_post_repair_state
        plan = _approved_plan()
        pre = capture_pre_repair_state(plan, tmp_path)
        dummy.write_text("# v2 modified\n")
        post = capture_post_repair_state(plan, tmp_path)

        assert pre["snapshots"][0]["sha256_before"] != post["snapshots"][0]["sha256_after"]


# ---------------------------------------------------------------------------
# Suite D: Execution and Verification
# ---------------------------------------------------------------------------

class TestExecutionAndVerification:

    def test_execute_repair_plan_records_actions(self):
        from core.audit.drift_repair_executor import execute_repair_plan
        plan = _approved_plan()
        result = execute_repair_plan(plan, "boss")
        assert result["executed_actions"] == plan["proposed_actions"]
        assert result["operator_id"] == "boss"

    def test_run_post_repair_verification_returns_valid_status(self, tmp_path):
        td = str(tmp_path / "runtime")
        os.makedirs(td, exist_ok=True)
        os.environ["LUKA_RUNTIME_ROOT"] = td

        from core.audit.drift_repair_executor import run_post_repair_verification
        plan = _approved_plan()
        execution = {"executed_actions": ["add import statement"]}
        pre_state = {"snapshots": [{"path": "core/audit/test_dummy.py", "sha256_before": "abc"}]}
        post_state = {"snapshots": [{"path": "core/audit/test_dummy.py", "sha256_after": "def"}]}

        result = run_post_repair_verification(plan, execution, pre_state, post_state)
        assert result["verification_status"] in ("PASSED", "FAILED", "INCONCLUSIVE")
        assert "checks" in result

    def test_run_post_repair_verification_fails_if_no_actions(self):
        from core.audit.drift_repair_executor import run_post_repair_verification
        plan = _approved_plan()
        result = run_post_repair_verification(plan, {"executed_actions": []}, {}, {})
        assert result["verification_status"] == "FAILED"


# ---------------------------------------------------------------------------
# Suite E: End-to-End Integration
# ---------------------------------------------------------------------------

class TestEndToEndIntegration:

    def _write_plan(self, td: str, plan: dict) -> None:
        state = Path(td) / "state"
        state.mkdir(parents=True, exist_ok=True)
        plans_path = state / "drift_repair_plans.jsonl"
        with plans_path.open("a") as fh:
            fh.write(json.dumps(plan) + "\n")

    def test_run_creates_execution_log_entry(self):
        td = _make_tmpdir()
        plan = _approved_plan()
        self._write_plan(td, plan)

        from core.audit.drift_repair_executor import run_supervised_repair_execution
        from core.audit.repair_execution_store import list_execution_records
        result = run_supervised_repair_execution("plan-test-001", "boss", td)
        records = list_execution_records(td)
        assert len(records) == 1
        assert records[0]["plan_id"] == "plan-test-001"

    def test_run_writes_latest_summary(self):
        td = _make_tmpdir()
        plan = _approved_plan()
        self._write_plan(td, plan)

        from core.audit.drift_repair_executor import run_supervised_repair_execution
        from core.audit.repair_execution_store import load_repair_execution_latest
        run_supervised_repair_execution("plan-test-001", "boss", td)
        latest = load_repair_execution_latest(td)
        assert latest.get("plan_id") == "plan-test-001"
        assert latest.get("operator_id") == "boss"

    def test_run_returns_execution_id(self):
        td = _make_tmpdir()
        self._write_plan(td, _approved_plan())
        from core.audit.drift_repair_executor import run_supervised_repair_execution
        result = run_supervised_repair_execution("plan-test-001", "boss", td)
        assert "execution_id" in result
        assert result["execution_id"].startswith("repair-exec-")

    def test_run_not_found_returns_failed(self):
        td = _make_tmpdir()
        from core.audit.drift_repair_executor import run_supervised_repair_execution
        result = run_supervised_repair_execution("nonexistent-plan", "boss", td)
        assert result["ok"] is False
        assert result["status"] == "FAILED"

    def test_api_run_returns_200_for_approved_plan(self):
        td = _make_tmpdir()
        plan = _approved_plan()
        state = Path(td) / "state"
        plans_path = state / "drift_repair_plans.jsonl"
        plans_path.write_text(json.dumps(plan) + "\n")
        os.environ["LUKA_RUNTIME_ROOT"] = td

        from interface.operator.api_drift_repair_execution import drift_repair_execution_run
        req = _mock_request({"plan_id": "plan-test-001", "operator_id": "boss"})
        resp = asyncio.run(drift_repair_execution_run(req))
        data = json.loads(resp.body)
        assert data.get("execution_id", "").startswith("repair-exec-")

    def test_api_history_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_drift_repair_execution import drift_repair_execution_history
        result = asyncio.run(drift_repair_execution_history())
        assert result["ok"] is True
        assert "records" in result

    def test_api_latest_returns_json(self):
        td = _make_tmpdir()
        from interface.operator.api_drift_repair_execution import drift_repair_execution_latest
        result = asyncio.run(drift_repair_execution_latest())
        assert result["ok"] is True
        assert "latest" in result

    def test_api_by_id_not_found(self):
        td = _make_tmpdir()
        from interface.operator.api_drift_repair_execution import drift_repair_execution_by_id
        result = asyncio.run(drift_repair_execution_by_id("nonexistent"))
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Suite F: Safety Invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:

    def _write_plan(self, td: str, plan: dict) -> None:
        state = Path(td) / "state"
        state.mkdir(parents=True, exist_ok=True)
        plans_path = state / "drift_repair_plans.jsonl"
        with plans_path.open("a") as fh:
            fh.write(json.dumps(plan) + "\n")

    def test_executor_does_not_run_unapproved_plan(self):
        td = _make_tmpdir()
        plan = _proposed_plan()
        self._write_plan(td, plan)
        from core.audit.drift_repair_executor import run_supervised_repair_execution
        from core.audit.repair_execution_store import list_execution_records
        result = run_supervised_repair_execution("plan-test-001", "boss", td)
        assert result["status"] == "FAILED"
        records = list_execution_records(td)
        # An execution record is written even for blocked executions (audit trail)
        assert all(r.get("scope_verdict") != "ALLOW" or r.get("status") == "EXECUTED"
                   for r in records)

    def test_executor_does_not_modify_audit_baseline(self):
        td = _make_tmpdir()
        baseline_path = Path(__file__).parent.parent / "audit" / "audit_baseline.py"
        mtime_before = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        plan = _approved_plan()
        self._write_plan(td, plan)
        from core.audit.drift_repair_executor import run_supervised_repair_execution
        run_supervised_repair_execution("plan-test-001", "boss", td)
        mtime_after = baseline_path.stat().st_mtime if baseline_path.exists() else 0
        assert mtime_before == mtime_after

    def test_executor_does_not_modify_drift_finding_status(self):
        td = _make_tmpdir()
        state = Path(td) / "state"
        status_path = state / "drift_finding_status.json"
        status_path.write_text(json.dumps({"finding-test-001": {"status": "ESCALATED"}}))
        mtime_before = status_path.stat().st_mtime

        plan = _approved_plan()
        self._write_plan(td, plan)
        from core.audit.drift_repair_executor import run_supervised_repair_execution
        run_supervised_repair_execution("plan-test-001", "boss", td)
        mtime_after = status_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_executor_does_not_modify_governance_log(self):
        td = _make_tmpdir()
        state = Path(td) / "state"
        log_path = state / "drift_governance_log.jsonl"
        log_path.write_text('{"action": "existing"}\n')
        mtime_before = log_path.stat().st_mtime

        plan = _approved_plan()
        self._write_plan(td, plan)
        from core.audit.drift_repair_executor import run_supervised_repair_execution
        run_supervised_repair_execution("plan-test-001", "boss", td)
        mtime_after = log_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_api_run_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_drift_repair_execution import drift_repair_execution_run
        req = _mock_request({"plan_id": "plan-test-001"})
        resp = asyncio.run(drift_repair_execution_run(req))
        assert resp.status_code == 403

    def test_api_verify_requires_operator_id(self):
        td = _make_tmpdir()
        from interface.operator.api_drift_repair_execution import drift_repair_execution_verify
        req = _mock_request({"execution_id": "exec-001"})
        resp = asyncio.run(drift_repair_execution_verify(req))
        assert resp.status_code == 403

    def test_list_approved_plans_returns_only_approved(self):
        td = _make_tmpdir()
        state = Path(td) / "state"
        plans_path = state / "drift_repair_plans.jsonl"
        approved = _approved_plan(plan_id="plan-a")
        proposed = _proposed_plan(plan_id="plan-b")
        with plans_path.open("w") as fh:
            fh.write(json.dumps(approved) + "\n")
            fh.write(json.dumps(proposed) + "\n")

        from core.audit.drift_repair_executor import list_approved_repair_plans
        result = list_approved_repair_plans(td)
        assert len(result) == 1
        assert result[0]["plan_id"] == "plan-a"

    def test_executor_outputs_limited_to_execution_files(self):
        td = _make_tmpdir()
        state = Path(td) / "state"
        plan = _approved_plan()
        self._write_plan(td, plan)
        from core.audit.drift_repair_executor import run_supervised_repair_execution
        run_supervised_repair_execution("plan-test-001", "boss", td)
        # Only execution log + latest should be written (+ plans.jsonl already existed)
        written = {f.name for f in state.iterdir()}
        allowed = {
            "drift_repair_plans.jsonl",
            "drift_repair_execution_log.jsonl",
            "drift_repair_execution_latest.json",
        }
        unexpected = written - allowed
        assert not unexpected, f"unexpected files written: {unexpected}"
