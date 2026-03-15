"""AG-24B: Topology transition gate — prevents unsafe config/process changes.

Enforces that topology-sensitive changes only happen when the system is STABLE
and that transitions are recorded and sequenced correctly.

State files:
  $LUKA_RUNTIME_ROOT/state/topology_transition_log.jsonl
  $LUKA_RUNTIME_ROOT/state/topology_mode.json

Modes: STABLE | DRAINING | TRANSITIONING | LOCKDOWN
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODES = frozenset({"STABLE", "DRAINING", "TRANSITIONING", "LOCKDOWN"})
_DEFAULT_MODE = "STABLE"

_LOG_NAME = "topology_transition_log.jsonl"
_MODE_FILE = "topology_mode.json"

# Actions that are sensitive to topology state
_TOPOLOGY_SENSITIVE_ACTIONS: frozenset[str] = frozenset({
    "policy_rollout", "rollout", "deploy", "config_change",
    "daemon_restart", "plist_update", "service_reload",
    "launchd_change", "mcp_config_change",
})


def _state_root() -> Path | None:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        return None
    return Path(raw) / "state"


def _read_mode() -> str:
    root = _state_root()
    if root is None:
        return _DEFAULT_MODE
    path = root / _MODE_FILE
    if not path.exists():
        return _DEFAULT_MODE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        mode = str(data.get("mode") or _DEFAULT_MODE).upper()
        return mode if mode in MODES else _DEFAULT_MODE
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_MODE


def _write_mode(mode: str) -> None:
    root = _state_root()
    if root is None or mode not in MODES:
        return
    root.mkdir(parents=True, exist_ok=True)
    path = root / _MODE_FILE
    tmp = path.with_suffix(".json.tmp")
    record = {
        "mode": mode,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        tmp.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        logger.warning("topology_mode write failed: %s", exc)


def _log_transition(change_request: dict[str, Any], verdict: str) -> None:
    root = _state_root()
    if root is None:
        return
    root.mkdir(parents=True, exist_ok=True)
    record = {
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verdict": verdict,
        **{k: v for k, v in change_request.items() if k in ("action", "target", "reason", "requester")},
    }
    try:
        log = root / _LOG_NAME
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError as exc:
        logger.warning("topology_transition_log write failed: %s", exc)


def get_topology_mode() -> str:
    """Return current topology mode string."""
    return _read_mode()


def set_topology_mode(mode: str) -> None:
    """Directly set topology mode (used by maintenance workflows only)."""
    if mode not in MODES:
        raise ValueError(f"Invalid topology mode: {mode!r}")
    _write_mode(mode)


def evaluate_transition(change_request: dict[str, Any]) -> str:
    """Evaluate whether a topology-sensitive change can proceed.

    Args:
        change_request: Dict with at least {"action": str}.
          Optional keys: target, reason, requester.

    Returns:
        "ALLOW" | "BLOCK" | "DRAIN_REQUIRED"
    """
    action = str(change_request.get("action") or "").lower().strip()
    mode = _read_mode()

    # Non-topology-sensitive action — always allow
    if action not in _TOPOLOGY_SENSITIVE_ACTIONS:
        _log_transition(change_request, "ALLOW")
        return "ALLOW"

    # LOCKDOWN — hard block everything
    if mode == "LOCKDOWN":
        logger.warning("topology_gate BLOCK: mode=LOCKDOWN action=%s", action)
        _log_transition(change_request, "BLOCK")
        return "BLOCK"

    # DRAINING or TRANSITIONING — drain first
    if mode in ("DRAINING", "TRANSITIONING"):
        logger.info("topology_gate DRAIN_REQUIRED: mode=%s action=%s", mode, action)
        _log_transition(change_request, "DRAIN_REQUIRED")
        return "DRAIN_REQUIRED"

    # STABLE — allow
    _log_transition(change_request, "ALLOW")
    return "ALLOW"
