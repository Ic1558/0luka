"""AG-61: Recommendation State Machine."""
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

def _atomic_write(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

def _append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")

def _read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

def _now():
    return datetime.now(timezone.utc).isoformat()

def _load_latest_map() -> dict:
    p = _state_dir() / "runtime_recommendation_state_latest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def _save_latest_map(m: dict):
    _atomic_write(_state_dir() / "runtime_recommendation_state_latest.json", m)


def create_recommendation(recommendation_id: str, trace_id: str | None = None) -> dict:
    from runtime.recommendation_state_policy import INITIAL_STATE
    record = {
        "recommendation_id": recommendation_id,
        "trace_id": trace_id,
        "state": INITIAL_STATE,
        "history": [{"state": INITIAL_STATE, "ts": _now()}],
        "ts_created": _now(),
        "ts_updated": _now(),
    }
    _persist(recommendation_id, record)
    return record


def transition(recommendation_id: str, new_state: str) -> dict:
    from runtime.recommendation_state_policy import TRANSITIONS, TERMINAL_STATES
    latest = _load_latest_map()
    record = latest.get(recommendation_id)
    if record is None:
        raise ValueError(f"recommendation_id not found: {recommendation_id}")
    current = record["state"]
    if current in TERMINAL_STATES:
        raise ValueError(f"State {current} is terminal — no transitions allowed")
    allowed = TRANSITIONS.get(current, [])
    if new_state not in allowed:
        raise ValueError(f"Illegal transition {current} -> {new_state}. Allowed: {allowed}")
    record["state"] = new_state
    record["history"].append({"state": new_state, "ts": _now()})
    record["ts_updated"] = _now()
    _persist(recommendation_id, record)
    return record


def get_state(recommendation_id: str) -> dict | None:
    return _load_latest_map().get(recommendation_id)


def list_states() -> list:
    sd = _state_dir()
    idx = sd / "runtime_recommendation_state_index.json"
    if not idx.exists():
        return []
    try:
        return json.loads(idx.read_text())
    except Exception:
        return []


def _persist(recommendation_id: str, record: dict):
    sd = _state_dir()
    latest = _load_latest_map()
    latest[recommendation_id] = record
    _save_latest_map(latest)
    _append_jsonl(sd / "runtime_recommendation_state_log.jsonl", record)
    idx_path = sd / "runtime_recommendation_state_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    if not any(e["recommendation_id"] == recommendation_id for e in idx):
        idx.append({"recommendation_id": recommendation_id, "ts_created": record["ts_created"]})
    _atomic_write(idx_path, idx)
