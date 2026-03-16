"""AG-71 tests: Multi-Agent Execution Contract."""
import os, sys, json
import pytest
sys.path.insert(0, "/Users/icmini/0luka")

VALID_TASK = {
    "task_id": "t001",
    "actor_id": "claude",
    "authority_level": "WRITE",
    "trace_id": "tr001",
}


def test_register_valid_task(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.multi_agent_contract import register_contract_task
    rec = register_contract_task(VALID_TASK)
    assert rec["valid"] is True
    assert rec["validation_reason"] == "ok"


def test_register_missing_field(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.multi_agent_contract import register_contract_task
    bad = {"task_id": "t002", "actor_id": "gpt"}  # missing authority_level + trace_id
    rec = register_contract_task(bad)
    assert rec["valid"] is False
    assert "missing_field" in rec["validation_reason"]


def test_register_invalid_authority(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.multi_agent_contract import register_contract_task
    bad = {**VALID_TASK, "authority_level": "SUPERUSER"}
    rec = register_contract_task(bad)
    assert rec["valid"] is False
    assert "invalid_authority_level" in rec["validation_reason"]


def test_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.multi_agent_contract import register_contract_task
    register_contract_task(VALID_TASK)
    assert (tmp_path / "state" / "runtime_multi_agent_contract_latest.json").exists()
    assert (tmp_path / "state" / "runtime_multi_agent_contract_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_multi_agent_contract_index.json").exists()


def test_validate_result(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.multi_agent_contract import validate_result
    valid, reason = validate_result({
        "task_id": "t001", "actor_id": "claude",
        "status": "COMPLETED", "trace_id": "tr001"
    })
    assert valid is True
    valid2, reason2 = validate_result({"task_id": "t001", "actor_id": "x", "status": "DONE", "trace_id": "t"})
    assert valid2 is False
