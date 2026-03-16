"""AG-65 tests: Runtime Replay / Time Travel Debug."""
import json, os, sys
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_replay_empty_trace(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.runtime_replay import replay
    r = replay("trace_empty", "op1")
    assert r["replay_id"]
    assert r["trace_id"] == "trace_empty"
    assert r["read_only"] is True


def test_replay_is_read_only(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.runtime_replay import replay
    r = replay("trace_ro", "op1")
    assert r["read_only"] is True


def test_replay_order(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    sd = tmp_path / "state"
    sd.mkdir()
    (sd / "runtime_recommendation_trace_log.jsonl").write_text(
        json.dumps({"trace_id": "trace_ord", "recommendation_id": "rec_ord",
                    "ts_created": "2026-01-01T00:00:00Z"}) + "\n"
    )
    from runtime.audit_graph import build_graph
    build_graph("trace_ord")
    from runtime.runtime_replay import replay
    r = replay("trace_ord", "op1")
    ts_list = [n.get("ts", "") for n in r["events_replayed"]]
    assert ts_list == sorted(ts_list)
    assert r["replay_order_verified"] is True


def test_replay_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.runtime_replay import replay
    replay("trace_art", "op1")
    assert (tmp_path / "state" / "runtime_replay_latest.json").exists()
    assert (tmp_path / "state" / "runtime_replay_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_replay_index.json").exists()


def test_replay_does_not_mutate_other_stores(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.runtime_replay import replay
    replay("trace_nomut", "op1")
    replay("trace_nomut", "op1")
    # Decision/trace stores must not be created by replay
    assert not (tmp_path / "state" / "runtime_operator_decision_record_log.jsonl").exists()
    # Replay log has 2 entries (two replays)
    log = (tmp_path / "state" / "runtime_replay_log.jsonl").read_text().splitlines()
    assert len(log) == 2
