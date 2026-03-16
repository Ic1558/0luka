"""AG-64 tests: Cross-Layer Audit Graph."""
import json, os, sys
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_build_empty_graph(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.audit_graph import build_graph
    g = build_graph("trace_empty")
    assert g["trace_id"] == "trace_empty"
    assert g["graph_id"]
    assert isinstance(g["nodes"], list)
    assert isinstance(g["edges"], list)


def test_build_graph_with_nodes(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    sd = tmp_path / "state"
    sd.mkdir()
    (sd / "runtime_recommendation_trace_log.jsonl").write_text(
        json.dumps({"trace_id": "trace_full", "recommendation_id": "rec_001", "ts_created": "2026-01-01T00:00:00Z"}) + "\n"
    )
    (sd / "runtime_operator_decision_record_log.jsonl").write_text(
        json.dumps({"trace_id": "trace_full", "decision_record_id": "dr_001",
                    "recommendation_id": "rec_001", "ts_actioned": "2026-01-01T00:01:00Z"}) + "\n"
    )
    from runtime.audit_graph import build_graph
    g = build_graph("trace_full")
    assert len(g["nodes"]) >= 2
    types = {n["node_type"] for n in g["nodes"]}
    assert "recommendation" in types
    assert "operator_decision" in types


def test_edges_connect_nodes(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    sd = tmp_path / "state"
    sd.mkdir()
    (sd / "runtime_recommendation_trace_log.jsonl").write_text(
        json.dumps({"trace_id": "trace_edge", "recommendation_id": "rec_e1", "ts_created": "2026-01-01T00:00:00Z"}) + "\n"
    )
    (sd / "runtime_operator_decision_record_log.jsonl").write_text(
        json.dumps({"trace_id": "trace_edge", "decision_record_id": "dr_e1",
                    "recommendation_id": "rec_e1", "ts_actioned": "2026-01-01T00:01:00Z"}) + "\n"
    )
    from runtime.audit_graph import build_graph
    g = build_graph("trace_edge")
    assert len(g["edges"]) >= 1
    node_ids = {n["node_id"] for n in g["nodes"]}
    for e in g["edges"]:
        assert e["from_node"] in node_ids
        assert e["to_node"] in node_ids


def test_lookup_by_trace_id(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.audit_graph import build_graph, get_graph
    build_graph("trace_lookup")
    g = get_graph("trace_lookup")
    assert g is not None
    assert g["trace_id"] == "trace_lookup"


def test_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.audit_graph import build_graph
    build_graph("trace_art")
    assert (tmp_path / "state" / "runtime_audit_graph_latest.json").exists()
    assert (tmp_path / "state" / "runtime_audit_graph_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_audit_graph_index.json").exists()
