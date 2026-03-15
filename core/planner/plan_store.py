"""AG-19: Plan persistence — backed by $LUKA_RUNTIME_ROOT/state/."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

_LOG_NAME = "plan_log.jsonl"
_LATEST_NAME = "plan_latest.json"


def _state_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        raise RuntimeError("LUKA_RUNTIME_ROOT is required (fail-closed)")
    return Path(raw) / "state"


def append_plan(plan: dict[str, Any]) -> None:
    """Append plan record to plan_log.jsonl (append-only)."""
    path = _state_root() / _LOG_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(plan, sort_keys=True) + "\n")
    except OSError as exc:
        raise RuntimeError(f"plan_log_write_failed: {exc}") from exc


def write_latest(plan: dict[str, Any]) -> None:
    """Atomically overwrite plan_latest.json."""
    path = _state_root() / _LATEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        raise RuntimeError(f"plan_latest_write_failed: {exc}") from exc


def get_latest() -> Optional[dict[str, Any]]:
    path = _state_root() / _LATEST_NAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_recent(limit: int = 50) -> list[dict[str, Any]]:
    path = _state_root() / _LOG_NAME
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items: list[dict[str, Any]] = []
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
