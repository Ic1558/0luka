"""AG-24A: Emergency stop — operator kill-switch for the live autonomy path.

When active:
  - feedback_loop cannot act (execute, adapt, rollout)
  - rollout_manager cannot proceed
  - remediation cannot fire
  - read-only APIs and escalation surfaces remain available

State file: $LUKA_RUNTIME_ROOT/state/emergency_stop.json
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STATE_FILE = "emergency_stop.json"


def _state_path() -> Path | None:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        return None
    return Path(raw) / "state" / _STATE_FILE


def _read_state() -> dict[str, Any]:
    path = _state_path()
    if path is None or not path.exists():
        return {"active": False, "reason": None, "activated_at": None,
                "cleared_at": None, "cleared_by": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # Fail-closed: unreadable state = treat as active stop
        logger.warning("emergency_stop state unreadable — fail-closed (treating as active)")
        return {"active": True, "reason": "state_unreadable", "activated_at": None,
                "cleared_at": None, "cleared_by": None}


def _write_state(state: dict[str, Any]) -> None:
    path = _state_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        logger.warning("emergency_stop write failed: %s", exc)


def is_emergency_stop_active() -> bool:
    """Return True if emergency stop is currently active.

    Fail-closed: if state file is unreadable, returns True.
    If LUKA_RUNTIME_ROOT is unset, returns False (no runtime = no stop).
    """
    path = _state_path()
    if path is None:
        return False
    return bool(_read_state().get("active", False))


def activate_emergency_stop(reason: str) -> None:
    """Activate emergency stop. Idempotent — safe to call when already active."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state = _read_state()
    if state.get("active"):
        logger.info("emergency_stop already active (reason=%s)", state.get("reason"))
        return
    _write_state({
        "active": True,
        "reason": reason,
        "activated_at": ts,
        "cleared_at": None,
        "cleared_by": None,
    })
    logger.warning("EMERGENCY STOP ACTIVATED: %s", reason)


def clear_emergency_stop(operator_id: str) -> None:
    """Clear emergency stop. Only takes effect if currently active."""
    state = _read_state()
    if not state.get("active"):
        logger.info("emergency_stop already inactive — nothing to clear")
        return
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write_state({
        "active": False,
        "reason": state.get("reason"),
        "activated_at": state.get("activated_at"),
        "cleared_at": ts,
        "cleared_by": operator_id,
    })
    logger.info("EMERGENCY STOP CLEARED by %s", operator_id)


def get_emergency_stop_state() -> dict[str, Any]:
    """Return the full emergency stop state dict."""
    return _read_state()
