"""AG-24B: Autonomy budget — per-run action depth limits for the live control plane.

Tracks and enforces hard limits on how many times each action type can fire
within a single run. All budgets are checked before any action executes.

State files:
  $LUKA_RUNTIME_ROOT/state/autonomy_budget.jsonl  — append-only log
  $LUKA_RUNTIME_ROOT/state/autonomy_budget_latest.json — current snapshot
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hard budget ceilings — set by CLC, not configurable at runtime
# ---------------------------------------------------------------------------
_CEILINGS: dict[str, int] = {
    "decision_depth": 1,
    "retry": 1,
    "fallback": 1,
    "adaptation_depth": 2,
    "policy_rollout_steps": 1,
}

_LOG_NAME = "autonomy_budget.jsonl"
_LATEST_NAME = "autonomy_budget_latest.json"


def _state_root() -> Path | None:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        return None
    return Path(raw) / "state"


def _budget_id(run_id: str) -> str:
    return "bgt_" + hashlib.sha256(run_id.encode()).hexdigest()[:12]


def _empty_budget(run_id: str) -> dict[str, Any]:
    return {
        "budget_id": _budget_id(run_id),
        "run_id": run_id,
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ceilings": dict(_CEILINGS),
        "consumed": {k: 0 for k in _CEILINGS},
        "status": "ACTIVE",
    }


def _load_budget(run_id: str) -> dict[str, Any]:
    root = _state_root()
    if root is None:
        return _empty_budget(run_id)
    latest = root / _LATEST_NAME
    if not latest.exists():
        return _empty_budget(run_id)
    try:
        rec = json.loads(latest.read_text(encoding="utf-8"))
        if rec.get("run_id") == run_id:
            return rec
    except (OSError, json.JSONDecodeError):
        pass
    return _empty_budget(run_id)


def _save_budget(budget: dict[str, Any]) -> None:
    root = _state_root()
    if root is None:
        return
    root.mkdir(parents=True, exist_ok=True)
    try:
        log = root / _LOG_NAME
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(budget, sort_keys=True) + "\n")
        latest = root / _LATEST_NAME
        tmp = latest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(budget, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, latest)
    except OSError as exc:
        logger.warning("autonomy_budget save failed: %s", exc)


def get_autonomy_budget(run_id: str) -> dict[str, Any]:
    """Return the current budget state for run_id (creates fresh if not exists)."""
    return _load_budget(run_id)


def consume_budget(run_id: str, action_type: str) -> bool:
    """Consume one unit of action_type budget for run_id.

    Returns True if consumption was allowed, False if budget already exhausted.
    Persists the updated budget state.
    """
    budget = _load_budget(run_id)
    if budget.get("status") == "EXHAUSTED":
        return False

    consumed = budget.get("consumed", {})
    ceilings = budget.get("ceilings", _CEILINGS)
    current = consumed.get(action_type, 0)
    ceiling = ceilings.get(action_type, 0)

    if current >= ceiling:
        logger.warning("budget exhausted: run=%s action=%s (%d/%d)", run_id, action_type, current, ceiling)
        budget["status"] = "EXHAUSTED"
        _save_budget(budget)
        return False

    consumed[action_type] = current + 1
    budget["consumed"] = consumed
    budget["ts_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Check if all budgets now exhausted
    all_exhausted = all(
        consumed.get(k, 0) >= ceilings.get(k, 0) for k in ceilings
    )
    if all_exhausted:
        budget["status"] = "EXHAUSTED"

    _save_budget(budget)
    return True


def budget_exhausted(run_id: str) -> bool:
    """Return True if any budget slot is at ceiling for run_id."""
    budget = _load_budget(run_id)
    if budget.get("status") == "EXHAUSTED":
        return True
    consumed = budget.get("consumed", {})
    ceilings = budget.get("ceilings", _CEILINGS)
    return any(consumed.get(k, 0) >= ceilings.get(k, 1) for k in ceilings)


def get_budget_state(run_id: str) -> dict[str, Any]:
    """Return full budget state with remaining units per action type."""
    budget = _load_budget(run_id)
    consumed = budget.get("consumed", {})
    ceilings = budget.get("ceilings", _CEILINGS)
    remaining = {k: max(0, ceilings.get(k, 0) - consumed.get(k, 0)) for k in ceilings}
    return {**budget, "remaining": remaining}
