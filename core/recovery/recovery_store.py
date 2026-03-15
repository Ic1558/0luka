"""AG-28: Recovery store — append-only log + atomic latest pointer.

State files (under LUKA_RUNTIME_ROOT/state/):
  recovery_log.jsonl        append-only history
  recovery_latest.json      atomic pointer to latest record
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import RUNTIME_ROOT

_STATE_DIR = RUNTIME_ROOT / "state"


def _state_dir() -> Path:
    d = _STATE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log_path() -> Path:
    return _state_dir() / "recovery_log.jsonl"


def _latest_path() -> Path:
    return _state_dir() / "recovery_latest.json"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_recovery(record: dict[str, Any]) -> dict[str, Any]:
    """Append a recovery record to the log.

    Adds recovery_id and ts if not present.
    Returns the completed record.
    """
    if "recovery_id" not in record:
        record = dict(record, recovery_id=uuid.uuid4().hex[:12])
    if "ts" not in record:
        record = dict(record, ts=_now_utc())

    log_path = _log_path()
    existing = log_path.read_text() if log_path.exists() else ""
    tmp = log_path.with_suffix(".tmp")
    tmp.write_text(existing + json.dumps(record) + "\n")
    tmp.replace(log_path)
    return record


def write_latest(record: dict[str, Any]) -> None:
    """Atomically write the latest recovery record."""
    latest_path = _latest_path()
    tmp = latest_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=2))
    tmp.replace(latest_path)


def list_recent(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent recovery records."""
    log_path = _log_path()
    if not log_path.exists():
        return []
    records = []
    for ln in log_path.read_text().splitlines():
        if not ln.strip():
            continue
        try:
            records.append(json.loads(ln))
        except json.JSONDecodeError:
            pass
    return records[-limit:]


def get_latest() -> dict[str, Any] | None:
    """Return the latest recovery record, or None."""
    latest_path = _latest_path()
    if not latest_path.exists():
        return None
    try:
        return json.loads(latest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
