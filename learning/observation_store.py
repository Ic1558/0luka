"""AG-21: Observation store — append-only execution observation log.

Storage: $LUKA_RUNTIME_ROOT/state/learning_observations.jsonl

Rules:
  - append-only (no mutation, no deletion)
  - atomic writes via temp + rename
  - fail closed on write error (RuntimeError)
  - never blocks runtime (caller must wrap in try/except)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import os

from learning.models import ObservationRecord

_LOG_NAME = "learning_observations.jsonl"


def _log_path() -> Path:
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(runtime_root) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d / _LOG_NAME


def append_observation(record: ObservationRecord | dict[str, Any]) -> dict[str, Any]:
    """Append one observation to the log.

    Accepts ObservationRecord or plain dict.
    Returns the serialized record dict.
    """
    if isinstance(record, ObservationRecord):
        data = record.to_dict()
    else:
        data = dict(record)
    if not data.get("timestamp"):
        data["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not data.get("observation_id"):
        import uuid
        data["observation_id"] = uuid.uuid4().hex[:12]

    log_path = _log_path()
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    tmp = log_path.with_suffix(".tmp")
    tmp.write_text(existing + json.dumps(data) + "\n", encoding="utf-8")
    tmp.replace(log_path)
    return data


def get_recent_observations(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent observations (up to limit)."""
    log_path = _log_path()
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records[-limit:]


def get_observations_by_run(run_id: str) -> list[dict[str, Any]]:
    """Return all observations for a specific run_id."""
    return [r for r in get_recent_observations(limit=1000) if r.get("run_id") == run_id]
