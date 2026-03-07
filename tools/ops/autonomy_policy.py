#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import approval_state, memory_recovery, remediation_engine, worker_recovery

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
LANES = approval_state.LANES
ENV_GATES = {
    "memory_recovery": "LUKA_ALLOW_MEMORY_RECOVERY",
    "worker_recovery": "LUKA_ALLOW_WORKER_RECOVERY",
    "api_recovery": "LUKA_ALLOW_API_RESTART",
    "redis_recovery": "LUKA_ALLOW_REDIS_RESTART",
}


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _lane_availability(runtime_root: Path) -> dict[str, tuple[bool, str]]:
    memory_ok, memory_reason = memory_recovery._recovery_action_available(runtime_root)
    worker_ok, worker_reason = worker_recovery._recovery_action_available()
    api_ok = remediation_engine.API_RESTART_PATH.exists()
    api_reason = f"restart_path_present:{remediation_engine.API_RESTART_PATH}" if api_ok else f"restart_path_missing:{remediation_engine.API_RESTART_PATH}"
    return {
        "memory_recovery": (memory_ok, memory_reason),
        "worker_recovery": (worker_ok, worker_reason),
        "api_recovery": (api_ok, api_reason),
        "redis_recovery": (False, "no_safe_restart_path_configured"),
    }


def _approval_status(entry: dict[str, Any]) -> tuple[bool, str]:
    expires_at = _parse_ts(entry.get("expires_at"))
    if expires_at is not None and expires_at <= _utc_now():
        return False, "expired"
    if bool(entry.get("approved")):
        return True, "present"
    return False, "missing"


def _lane_payload(
    lane: str,
    entry: dict[str, Any],
    *,
    env_gate: str,
    available: bool,
    availability_reason: str,
) -> dict[str, Any]:
    env_present = os.environ.get(env_gate, "").strip() == "1"
    approved, approval_state_name = _approval_status(entry)
    expires_at = entry.get("expires_at")
    approved_by = entry.get("approved_by")

    if not available:
        status = "unavailable"
        reason = availability_reason
    elif not approved:
        status = "approval_required"
        reason = "approval_expired" if approval_state_name == "expired" else "approval_missing"
    elif not env_present:
        status = "approval_required"
        reason = f"env_gate_missing:{env_gate}"
    else:
        status = "allowed"
        reason = "approved_and_available"

    return {
        "status": status,
        "reason": reason,
        "approved": approved,
        "approval_state": approval_state_name,
        "approved_by": approved_by,
        "expires_at": expires_at,
        "env_gate": env_gate,
        "env_gate_present": env_present,
        "available": available,
        "availability_reason": availability_reason,
        "lane": lane,
    }


def evaluate_policy(*, runtime_root: Path | None = None, lane: str | None = None) -> dict[str, Any]:
    resolved_runtime_root = runtime_root or _runtime_root()
    availability = _lane_availability(resolved_runtime_root)
    try:
        approval_payload = approval_state.load_approval_state(runtime_root=resolved_runtime_root)
    except Exception as exc:
        lanes = {}
        for lane_name in LANES:
            if lane and lane_name != lane:
                continue
            available, availability_reason = availability[lane_name]
            lanes[lane_name] = {
                "status": "denied",
                "reason": str(exc),
                "approved": False,
                "approval_state": "invalid",
                "approved_by": None,
                "expires_at": None,
                "env_gate": ENV_GATES[lane_name],
                "env_gate_present": os.environ.get(ENV_GATES[lane_name], "").strip() == "1",
                "available": available,
                "availability_reason": availability_reason,
                "lane": lane_name,
            }
        return {
            "ok": True,
            "runtime_root": str(resolved_runtime_root),
            "approval_state": {
                "path": str(resolved_runtime_root / "state" / "approval_state.json"),
                "exists": (resolved_runtime_root / "state" / "approval_state.json").exists(),
                "valid": False,
            },
            "lanes": lanes,
            "errors": [str(exc)],
        }

    lanes = {}
    for lane_name in LANES:
        if lane and lane_name != lane:
            continue
        available, availability_reason = availability[lane_name]
        lanes[lane_name] = _lane_payload(
            lane_name,
            approval_payload["lanes"][lane_name],
            env_gate=ENV_GATES[lane_name],
            available=available,
            availability_reason=availability_reason,
        )
    return {
        "ok": True,
        "runtime_root": str(resolved_runtime_root),
        "approval_state": {
            "path": approval_payload["path"],
            "exists": approval_payload["exists"],
            "valid": True,
        },
        "lanes": lanes,
        "errors": [],
    }


def _render_human(payload: dict[str, Any], *, lane: str | None = None) -> str:
    lines = ["Autonomy Policy", "---------------"]
    if lane:
        lane_names = [lane]
    else:
        lane_names = list(payload.get("lanes", {}).keys())
    for lane_name in lane_names:
        item = payload["lanes"].get(lane_name, {})
        lines.extend(
            [
                "",
                lane_name,
                f"  status: {item.get('status', 'denied')}",
                f"  reason: {item.get('reason', 'unknown')}",
                f"  approval: {item.get('approval_state', 'invalid')}",
                f"  expires_at: {item.get('expires_at') or 'n/a'}",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the effective autonomy policy for remediation lanes.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--lane", choices=LANES, help="Render only one lane")
    args = parser.parse_args()

    payload = evaluate_policy(lane=args.lane)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    print(_render_human(payload, lane=args.lane))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
