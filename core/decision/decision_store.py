"""AG-18: Decision persistence backed by $LUKA_RUNTIME_ROOT/state/."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from core.decision.models import DecisionRecord

_LOG_NAME = "decision_log.jsonl"
_LATEST_NAME = "decision_latest.json"


def _state_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        raise RuntimeError("LUKA_RUNTIME_ROOT is required (fail-closed)")
    return Path(raw) / "state"


def _log_path() -> Path:
    return _state_root() / _LOG_NAME


def _latest_path() -> Path:
    return _state_root() / _LATEST_NAME


def append_decision(record: DecisionRecord) -> None:
    """Append record to decision_log.jsonl (append-only)."""
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    except OSError as exc:
        raise RuntimeError(f"decision_log_write_failed: {exc}") from exc


def write_latest(record: DecisionRecord) -> None:
    """Atomically overwrite decision_latest.json (temp + rename)."""
    path = _latest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        raise RuntimeError(f"decision_latest_write_failed: {exc}") from exc


def get_latest() -> Optional[dict]:
    """Return the latest decision record, or None if none exists."""
    path = _latest_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_recent(limit: int = 50) -> list[dict]:
    """Return the most recent `limit` decision records from the log."""
    path = _log_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    bounded = max(1, min(int(limit), 200))
    return items[-bounded:]
