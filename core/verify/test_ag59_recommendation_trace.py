"""AG-59 tests: Recommendation Lifecycle Trace."""
import os, sys
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_create_trace(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.recommendation_trace import create_trace
    t = create_trace("rec_001", "anomaly_learning")
    assert t["trace_id"]
    assert t["recommendation_id"] == "rec_001"
    assert t["source_phase"] == "anomaly_learning"


def test_update_trace(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.recommendation_trace import create_trace, update_trace, get_trace
    t = create_trace("rec_002", "policy_review")
    updated = update_trace(t["trace_id"], governance_id="gov_001")
    assert updated["governance_id"] == "gov_001"
    fetched = get_trace(t["trace_id"])
    assert fetched["governance_id"] == "gov_001"


def test_lifecycle_continuity(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.recommendation_trace import create_trace, update_trace, get_trace
    t = create_trace("rec_003", "chain_run")
    tid = t["trace_id"]
    update_trace(tid, governance_id="gov_x")
    update_trace(tid, decision_id="dec_x")
    update_trace(tid, memory_id="mem_x")
    final = get_trace(tid)
    assert final["governance_id"] == "gov_x"
    assert final["decision_id"] == "dec_x"
    assert final["memory_id"] == "mem_x"


def test_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.recommendation_trace import create_trace
    create_trace("rec_004", "test")
    assert (tmp_path / "state" / "runtime_recommendation_trace_latest.json").exists()
    assert (tmp_path / "state" / "runtime_recommendation_trace_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_recommendation_trace_index.json").exists()


def test_list_traces(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.recommendation_trace import create_trace, list_traces
    create_trace("rec_a", "phase_x")
    create_trace("rec_b", "phase_y")
    lst = list_traces()
    assert len(lst) == 2
