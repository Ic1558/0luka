"""AG-63 tests: Runtime Event Bus Normalization."""
import os, sys
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_emit_valid_event(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.event_bus_normalization import emit_event
    e = emit_event("trace_1", "recommendation", "rec_001", "clc", "create", "INFO", {"msg": "created"})
    assert e["event_id"]
    assert e["severity"] == "INFO"


def test_invalid_severity_fails(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.event_bus_normalization import emit_event
    with pytest.raises(ValueError):
        emit_event("trace_1", "recommendation", "rec_001", "clc", "create", "DEBUG", {"msg": "x"})


def test_missing_trace_id_fails(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.event_bus_normalization import emit_event
    with pytest.raises(ValueError):
        emit_event("", "recommendation", "rec_001", "clc", "create", "INFO", {"msg": "x"})


def test_three_entity_types(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.event_bus_normalization import emit_event, list_events
    emit_event("t1", "recommendation", "r1", "clc", "create", "INFO", {})
    emit_event("t2", "operator_decision", "d1", "op", "record", "INFO", {})
    emit_event("t3", "chain_run", "c1", "runner", "run", "WARN", {})
    events = list_events()
    types = {e["entity_type"] for e in events}
    assert "recommendation" in types
    assert "operator_decision" in types
    assert "chain_run" in types


def test_event_log_append_only(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.event_bus_normalization import emit_event
    emit_event("t1", "recommendation", "r1", "clc", "p1", "INFO", {})
    emit_event("t2", "operator_decision", "d1", "op", "p2", "INFO", {})
    log = (tmp_path / "state" / "runtime_event_bus_log.jsonl").read_text().splitlines()
    assert len(log) == 2


def test_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.event_bus_normalization import emit_event
    emit_event("t1", "recommendation", "r1", "clc", "p1", "INFO", {})
    assert (tmp_path / "state" / "runtime_event_bus_latest.json").exists()
    assert (tmp_path / "state" / "runtime_event_bus_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_event_bus_index.json").exists()
