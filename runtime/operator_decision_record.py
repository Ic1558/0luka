"""AG-60: Operator Decision Recording Interface."""
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


def record_decision(
    operator_id: str,
    action: str,
    reason: str,
    trace_id: str | None = None,
    governance_id: str | None = None,
    recommendation_id: str | None = None,
    evidence_refs: list | None = None,
) -> dict:
    from runtime.operator_decision_policy import ALLOWED_ACTIONS
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Invalid action '{action}'. Allowed: {ALLOWED_ACTIONS}")
    record = {
        "decision_record_id": str(uuid.uuid4()),
        "operator_id": operator_id,
        "action": action,
        "reason": reason,
        "trace_id": trace_id,
        "governance_id": governance_id,
        "recommendation_id": recommendation_id,
        "evidence_refs": evidence_refs or [],
        "ts_actioned": _now(),
    }
    sd = _state_dir()
    _atomic_write(sd / "runtime_operator_decision_record_latest.json", record)
    _append_jsonl(sd / "runtime_operator_decision_record_log.jsonl", record)
    idx_path = sd / "runtime_operator_decision_record_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({"decision_record_id": record["decision_record_id"], "operator_id": operator_id, "action": action, "ts_actioned": record["ts_actioned"]})
    _atomic_write(idx_path, idx)
    return record


def get_decision(decision_record_id: str) -> dict | None:
    sd = _state_dir()
    return next((r for r in _read_jsonl(sd / "runtime_operator_decision_record_log.jsonl") if r.get("decision_record_id") == decision_record_id), None)


def list_decisions() -> list:
    sd = _state_dir()
    idx = sd / "runtime_operator_decision_record_index.json"
    if not idx.exists():
        return []
    try:
        return json.loads(idx.read_text())
    except Exception:
        return []
