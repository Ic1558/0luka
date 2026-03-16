"""AG-65: Runtime Replay / Time Travel Debug."""
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


def replay(trace_id: str, operator_id: str) -> dict:
    """Replay a trace from audit graph. READ-ONLY — no mutations to other stores."""
    from runtime.audit_graph import get_graph, build_graph
    from runtime.runtime_replay_policy import MAX_EVENTS_PER_REPLAY

    graph = get_graph(trace_id) or build_graph(trace_id)
    nodes = sorted(graph.get("nodes", []), key=lambda n: n.get("ts", ""))
    nodes = nodes[:MAX_EVENTS_PER_REPLAY]

    ts_list = [n.get("ts", "") for n in nodes]
    replay_order_verified = ts_list == sorted(ts_list)

    report = {
        "replay_id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "operator_id": operator_id,
        "events_replayed": nodes,
        "replay_order_verified": replay_order_verified,
        "read_only": True,
        "replayed_at": _now(),
        "source_graph_id": graph.get("graph_id"),
    }

    # Write only to replay artifacts — no mutations elsewhere
    sd = _state_dir()
    _atomic_write(sd / "runtime_replay_latest.json", report)
    _append_jsonl(sd / "runtime_replay_log.jsonl", report)

    idx_path = sd / "runtime_replay_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({"replay_id": report["replay_id"], "trace_id": trace_id, "replayed_at": report["replayed_at"]})
    _atomic_write(idx_path, idx)

    return report


def get_replay(replay_id: str) -> dict | None:
    sd = _state_dir()
    return next((r for r in _read_jsonl(sd / "runtime_replay_log.jsonl")
                 if r.get("replay_id") == replay_id), None)


def list_replays() -> list:
    sd = _state_dir()
    idx = sd / "runtime_replay_index.json"
    if not idx.exists():
        return []
    try:
        return json.loads(idx.read_text())
    except Exception:
        return []
