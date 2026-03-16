"""AG-62 tests: Decision Memory Consolidation Layer."""
import json, os, sys
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_consolidate_empty_trace(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.decision_memory_consolidation import consolidate
    rec = consolidate("trace_empty")
    assert rec["trace_id"] == "trace_empty"
    assert rec["memory_id"]
    assert rec["sources"] == []


def test_consolidate_with_decision(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    # Write a fake decision record
    sd = tmp_path / "state"
    sd.mkdir()
    log = sd / "runtime_operator_decision_record_log.jsonl"
    log.write_text(json.dumps({"decision_record_id": "dr_001", "trace_id": "trace_abc", "action": "APPROVE"}) + "\n")

    from runtime.decision_memory_consolidation import consolidate
    rec = consolidate("trace_abc")
    assert len(rec["sources"]) == 1
    assert rec["sources"][0]["source_type"] == "operator_decision"
    assert "dr_001" in rec["decision_ids"]


def test_provenance_retained(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    sd = tmp_path / "state"
    sd.mkdir()
    log = sd / "runtime_recommendation_trace_log.jsonl"
    log.write_text(json.dumps({"trace_id": "trace_xyz", "recommendation_id": "rec_001", "governance_id": "gov_001"}) + "\n")

    from runtime.decision_memory_consolidation import consolidate
    rec = consolidate("trace_xyz")
    assert "rec_001" in rec["recommendation_ids"]
    assert "gov_001" in rec["governance_ids"]


def test_lookup_by_trace_id(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.decision_memory_consolidation import consolidate, get_memory
    consolidate("trace_lookup")
    m = get_memory("trace_lookup")
    assert m is not None
    assert m["trace_id"] == "trace_lookup"


def test_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.decision_memory_consolidation import consolidate
    consolidate("trace_art")
    assert (tmp_path / "state" / "runtime_decision_memory_latest.json").exists()
    assert (tmp_path / "state" / "runtime_decision_memory_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_decision_memory_index.json").exists()
