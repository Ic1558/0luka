"""AG-64: Cross-Layer Audit Graph."""
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timezone
from pathlib import Path


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _atomic_write(path: Path, data) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")

def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _node(node_type: str, entity_id: str, ts: str | None = None) -> dict:
    return {"node_id": str(uuid.uuid4()), "node_type": node_type, "entity_id": entity_id, "ts": ts or _now()}


def build_graph(trace_id: str) -> dict:
    """Build cross-layer audit graph for a trace_id."""
    sd = _state_dir()
    nodes: list[dict] = []
    edges: list[dict] = []

    # Recommendation traces
    rec_node_map: dict[str, dict] = {}
    for t in _read_jsonl(sd / "runtime_recommendation_trace_log.jsonl"):
        if t.get("trace_id") == trace_id:
            n = _node("recommendation", t.get("recommendation_id", ""), t.get("ts_created"))
            nodes.append(n)
            rec_node_map[t.get("recommendation_id", "")] = n

    # Operator decisions
    for d in _read_jsonl(sd / "runtime_operator_decision_record_log.jsonl"):
        if d.get("trace_id") == trace_id:
            n = _node("operator_decision", d.get("decision_record_id", ""), d.get("ts_actioned"))
            nodes.append(n)
            rec_id = d.get("recommendation_id", "")
            if rec_id in rec_node_map:
                edges.append({"from_node": rec_node_map[rec_id]["node_id"], "to_node": n["node_id"], "relation": "decides"})

    # Memory records
    for m in _read_jsonl(sd / "runtime_decision_memory_log.jsonl"):
        if m.get("trace_id") == trace_id:
            n = _node("memory_record", m.get("memory_id", ""), m.get("consolidated_at"))
            nodes.append(n)

    # Events
    for e in _read_jsonl(sd / "runtime_event_bus_log.jsonl"):
        if e.get("trace_id") == trace_id:
            n = _node("event", e.get("event_id", ""), e.get("ts"))
            nodes.append(n)

    graph = {
        "graph_id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "nodes": nodes,
        "edges": edges,
        "built_at": _now(),
    }

    _atomic_write(sd / "runtime_audit_graph_latest.json", graph)
    _append_jsonl(sd / "runtime_audit_graph_log.jsonl", graph)

    idx_path = sd / "runtime_audit_graph_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({"graph_id": graph["graph_id"], "trace_id": trace_id,
                "node_count": len(nodes), "built_at": graph["built_at"]})
    _atomic_write(idx_path, idx)

    return graph


def get_graph(trace_id: str) -> dict | None:
    sd = _state_dir()
    return next((r for r in reversed(_read_jsonl(sd / "runtime_audit_graph_log.jsonl"))
                 if r.get("trace_id") == trace_id), None)


def list_graphs() -> list:
    sd = _state_dir()
    idx = sd / "runtime_audit_graph_index.json"
    if not idx.exists():
        return []
    try:
        return json.loads(idx.read_text())
    except Exception:
        return []
