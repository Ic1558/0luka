"""AG-59: Recommendation Lifecycle Trace."""
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _atomic_write(path: Path, data: Any) -> None:
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


def create_trace(recommendation_id: str, source_phase: str) -> dict:
    sd = _state_dir()
    trace = {
        "trace_id": str(uuid.uuid4()),
        "recommendation_id": recommendation_id,
        "source_phase": source_phase,
        "governance_id": None,
        "decision_id": None,
        "memory_id": None,
        "audit_refs": [],
        "ts_created": _now(),
        "ts_updated": _now(),
    }
    _persist(trace)
    return trace


def update_trace(trace_id: str, **kwargs) -> dict:
    sd = _state_dir()
    traces = _read_jsonl(sd / "runtime_recommendation_trace_log.jsonl")
    trace = next((t for t in reversed(traces) if t.get("trace_id") == trace_id), None)
    if trace is None:
        raise ValueError(f"trace_id not found: {trace_id}")
    allowed = {"governance_id", "decision_id", "memory_id", "audit_refs"}
    for k, v in kwargs.items():
        if k in allowed:
            trace[k] = v
    trace["ts_updated"] = _now()
    _persist(trace)
    return trace


def get_trace(trace_id: str) -> dict | None:
    sd = _state_dir()
    traces = _read_jsonl(sd / "runtime_recommendation_trace_log.jsonl")
    return next((t for t in reversed(traces) if t.get("trace_id") == trace_id), None)


def list_traces() -> list:
    sd = _state_dir()
    idx = sd / "runtime_recommendation_trace_index.json"
    if not idx.exists():
        return []
    try:
        return json.loads(idx.read_text())
    except Exception:
        return []


def _persist(trace: dict) -> None:
    sd = _state_dir()
    _atomic_write(sd / "runtime_recommendation_trace_latest.json", trace)
    _append_jsonl(sd / "runtime_recommendation_trace_log.jsonl", trace)
    idx_path = sd / "runtime_recommendation_trace_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    entry = {"trace_id": trace["trace_id"], "recommendation_id": trace["recommendation_id"], "ts_created": trace["ts_created"]}
    if not any(e["trace_id"] == trace["trace_id"] for e in idx):
        idx.append(entry)
    _atomic_write(idx_path, idx)
