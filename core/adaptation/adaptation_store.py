"""AG-20: Adaptation store — append-only log + atomic latest pointer.

State files (under LUKA_RUNTIME_ROOT/state/):
  adaptation_log.jsonl          append-only history
  adaptation_latest.json        atomic pointer to latest record
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _state_dir() -> Path:
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(runtime_root) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log_path() -> Path:
    return _state_dir() / "adaptation_log.jsonl"


def _latest_path() -> Path:
    return _state_dir() / "adaptation_latest.json"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_adaptation(record: dict[str, Any]) -> dict[str, Any]:
    """Append an adaptation record to the log.

    Adds adaptation_id and ts_utc if not present.
    Returns the completed record.
    """
    if "adaptation_id" not in record:
        record = dict(record, adaptation_id=uuid.uuid4().hex[:12])
    if "ts_utc" not in record:
        record = dict(record, ts_utc=_now_utc())

    log_path = _log_path()
    tmp = log_path.with_suffix(".tmp")
    existing = log_path.read_text() if log_path.exists() else ""
    tmp.write_text(existing + json.dumps(record) + "\n")
    tmp.replace(log_path)
    return record


def write_latest(record: dict[str, Any]) -> None:
    """Atomically write the latest adaptation record."""
    latest_path = _latest_path()
    tmp = latest_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=2))
    tmp.replace(latest_path)


def list_recent(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent adaptation records (newest last)."""
    log_path = _log_path()
    if not log_path.exists():
        return []
    lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
    records = []
    for ln in lines:
        try:
            records.append(json.loads(ln))
        except json.JSONDecodeError:
            pass
    return records[-limit:]


def get_latest() -> dict[str, Any] | None:
    """Return the latest adaptation record, or None."""
    latest_path = _latest_path()
    if not latest_path.exists():
        return None
    try:
        return json.loads(latest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
