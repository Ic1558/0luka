"""AG-60 tests: Operator Decision Recording Interface."""
import os, sys
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_all_action_types(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.operator_decision_record import record_decision
    for action in ["APPROVE", "REJECT", "RETAIN", "MODIFY"]:
        r = record_decision("op1", action, f"testing {action}")
        assert r["action"] == action
        assert r["decision_record_id"]


def test_invalid_action_fails(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.operator_decision_record import record_decision
    with pytest.raises(ValueError):
        record_decision("op1", "EXPLODE", "bad action")


def test_trace_linkage(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.operator_decision_record import record_decision, get_decision
    r = record_decision("op1", "APPROVE", "ok", trace_id="trace_xyz")
    fetched = get_decision(r["decision_record_id"])
    assert fetched["trace_id"] == "trace_xyz"


def test_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.operator_decision_record import record_decision
    record_decision("op1", "RETAIN", "keeping it")
    assert (tmp_path / "state" / "runtime_operator_decision_record_latest.json").exists()
    assert (tmp_path / "state" / "runtime_operator_decision_record_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_operator_decision_record_index.json").exists()
