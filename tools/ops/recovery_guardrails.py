#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
RATE_LIMIT_MAX = 3
RATE_LIMIT_WINDOW_SECONDS = 60
RETRY_LIMIT_MAX = 5
COOLDOWN_SECONDS = 60
LOOP_FAILURE_THRESHOLD = 3
BACKOFF_SCHEDULE = (2, 5, 10, 30)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime) -> str:
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _runtime_root(runtime_root: Path | None = None) -> Path:
    if runtime_root is not None:
        return runtime_root
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _state_path(runtime_root: Path | None = None) -> Path:
    return _runtime_root(runtime_root) / "state" / "recovery_guardrails.json"


def _lane_state() -> dict[str, Any]:
    return {
        "recent_executions": [],
        "cooldown_until": None,
        "halted": False,
        "failure_streak": {},
    }


def load_state(*, runtime_root: Path | None = None) -> dict[str, Any]:
    path = _state_path(runtime_root)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("guardrail_state_invalid")
    return payload


def save_state(state: dict[str, Any], *, runtime_root: Path | None = None) -> None:
    path = _state_path(runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ensure_lane(state: dict[str, Any], lane: str) -> dict[str, Any]:
    lane_state = state.get(lane)
    if not isinstance(lane_state, dict):
        lane_state = _lane_state()
    lane_state.setdefault("recent_executions", [])
    lane_state.setdefault("cooldown_until", None)
    lane_state.setdefault("halted", False)
    lane_state.setdefault("failure_streak", {})
    if not isinstance(lane_state["recent_executions"], list):
        lane_state["recent_executions"] = []
    if not isinstance(lane_state["failure_streak"], dict):
        lane_state["failure_streak"] = {}
    state[lane] = lane_state
    return lane_state


def _prune_recent(times: list[str], *, now: datetime) -> list[str]:
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    keep: list[str] = []
    for raw in times:
        parsed = _parse_iso(raw)
        if parsed is None:
            continue
        if parsed >= window_start:
            keep.append(_iso(parsed))
    return keep[-RATE_LIMIT_MAX:]


def backoff_seconds(attempt: int) -> int:
    idx = max(1, int(attempt)) - 1
    if idx >= len(BACKOFF_SCHEDULE):
        return BACKOFF_SCHEDULE[-1]
    return BACKOFF_SCHEDULE[idx]


def evaluate(
    *,
    lane: str,
    action: str,
    item_attempts: int,
    runtime_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or _utc_now()
    state = load_state(runtime_root=runtime_root)
    lane_state = _ensure_lane(state, lane)
    lane_state["recent_executions"] = _prune_recent(lane_state.get("recent_executions", []), now=current)

    if bool(lane_state.get("halted")):
        save_state(state, runtime_root=runtime_root)
        return {"allowed": False, "decision": "loop_protection_triggered", "queue_state": "blocked"}

    if int(item_attempts) >= RETRY_LIMIT_MAX:
        save_state(state, runtime_root=runtime_root)
        return {"allowed": False, "decision": "retry_limit_exceeded", "queue_state": "failed"}

    cooldown_until = _parse_iso(lane_state.get("cooldown_until"))
    if cooldown_until and cooldown_until > current:
        save_state(state, runtime_root=runtime_root)
        return {
            "allowed": False,
            "decision": "cooldown_active",
            "queue_state": "blocked",
            "cooldown_until": _iso(cooldown_until),
        }

    if len(lane_state["recent_executions"]) >= RATE_LIMIT_MAX:
        save_state(state, runtime_root=runtime_root)
        return {"allowed": False, "decision": "rate_limited", "queue_state": "blocked"}

    save_state(state, runtime_root=runtime_root)
    return {
        "allowed": True,
        "decision": "allowed",
        "queue_state": "running",
        "backoff_seconds": backoff_seconds(max(1, int(item_attempts) + 1)),
    }


def register_result(
    *,
    lane: str,
    action: str,
    result: str,
    runtime_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or _utc_now()
    state = load_state(runtime_root=runtime_root)
    lane_state = _ensure_lane(state, lane)
    lane_state["recent_executions"] = _prune_recent(lane_state.get("recent_executions", []), now=current)
    lane_state["recent_executions"].append(_iso(current))
    lane_state["recent_executions"] = lane_state["recent_executions"][-RATE_LIMIT_MAX:]

    failure_streak = lane_state.get("failure_streak", {})
    count = int(failure_streak.get(action, 0))
    decision = "recorded"

    if result == "success":
        lane_state["cooldown_until"] = _iso(current + timedelta(seconds=COOLDOWN_SECONDS))
        failure_streak[action] = 0
        decision = "cooldown_started"
    elif result == "failed":
        count += 1
        failure_streak[action] = count
        if count >= LOOP_FAILURE_THRESHOLD:
            lane_state["halted"] = True
            decision = "loop_protection_triggered"
        else:
            decision = "failure_recorded"
    else:
        decision = "non_execution_recorded"

    lane_state["failure_streak"] = failure_streak
    state[lane] = lane_state
    save_state(state, runtime_root=runtime_root)
    return {
        "ok": True,
        "decision": decision,
        "lane": lane,
        "action": action,
        "result": result,
        "halted": bool(lane_state.get("halted")),
        "cooldown_until": lane_state.get("cooldown_until"),
        "failure_count": int(lane_state.get("failure_streak", {}).get(action, 0)),
    }
