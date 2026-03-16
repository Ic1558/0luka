"""AG-63: Runtime Event Bus Normalization."""
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timezone
from pathlib import Path


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
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


def emit_event(
    trace_id: str,
    entity_type: str,
    entity_id: str,
    actor: str,
    phase: str,
    severity: str,
    payload: dict,
    evidence_refs: list | None = None,
) -> dict:
    from runtime.event_schema_policy import REQUIRED_FIELDS, ALLOWED_SEVERITIES
    if severity not in ALLOWED_SEVERITIES:
        raise ValueError(f"Invalid severity '{severity}'. Allowed: {ALLOWED_SEVERITIES}")
    vals = dict(trace_id=trace_id, entity_type=entity_type, entity_id=entity_id,
                actor=actor, phase=phase, severity=severity, payload=payload)
    for f in REQUIRED_FIELDS:
        v = vals.get(f)
        if v is None or v == "":
            raise ValueError(f"Missing required field: {f}")

    event_id = str(uuid.uuid4())
    if not event_id:
        raise RuntimeError("event_id generation failed")
    event = {
        "event_id": event_id,
        "trace_id": trace_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "actor": actor,
        "phase": phase,
        "severity": severity,
        "ts": _now(),
        "payload": payload,
        "evidence_refs": evidence_refs or [],
    }

    sd = _state_dir()
    _atomic_write(sd / "runtime_event_bus_latest.json", event)
    _append_jsonl(sd / "runtime_event_bus_log.jsonl", event)

    idx_path = sd / "runtime_event_bus_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({"event_id": event["event_id"], "entity_type": entity_type, "severity": severity, "ts": event["ts"]})
    _atomic_write(idx_path, idx)

    return event


def get_event(event_id: str) -> dict | None:
    sd = _state_dir()
    return next(
        (e for e in _read_jsonl(sd / "runtime_event_bus_log.jsonl") if e.get("event_id") == event_id),
        None,
    )


def list_events(limit: int = 50) -> list:
    sd = _state_dir()
    events = _read_jsonl(sd / "runtime_event_bus_log.jsonl")
    return events[-limit:]
