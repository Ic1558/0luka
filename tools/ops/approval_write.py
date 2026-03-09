#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import approval_state


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path("/Users/icmini/0luka_runtime")


def _approval_actions_log_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / "approval_actions.jsonl"


def _append_audit_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _audit_entry(*, timestamp: str, lane: str, action: str, actor: str, approved: bool, expires_at: str | None) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "lane": lane,
        "action": action,
        "actor": actor,
        "approved": approved,
        "expires_at": expires_at,
        "source": "approval_write",
    }


def write_approval_action(
    *,
    lane: str,
    actor: str,
    approve: bool = False,
    revoke: bool = False,
    expires_at: str | None = None,
    clear_expiry: bool = False,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    approval_state.validate_lane(lane)
    if not actor.strip():
        raise RuntimeError("approval_write_invalid:actor_required")
    if approve and revoke:
        raise RuntimeError("approval_write_invalid:approve_and_revoke")
    if expires_at and clear_expiry:
        raise RuntimeError("approval_write_invalid:expires_at_and_clear_expiry")
    if revoke and expires_at:
        raise RuntimeError("approval_write_invalid:revoke_with_expires_at")
    if not any([approve, revoke, expires_at is not None, clear_expiry]):
        raise RuntimeError("approval_write_invalid:no_action_selected")

    resolved_runtime_root = runtime_root or _runtime_root()
    state_payload = approval_state.load_approval_state(runtime_root=resolved_runtime_root)
    lanes = dict(state_payload["lanes"])
    lane_state = dict(lanes[lane])
    approval_state.parse_timestamp(expires_at, field="expires_at") if expires_at is not None else None

    timestamp = _utc_now()
    entries: list[dict[str, Any]] = []

    if approve:
        lane_state["approved"] = True
        lane_state["approved_by"] = actor
        lane_state["approved_at"] = timestamp
        entries.append(
            _audit_entry(
                timestamp=timestamp,
                lane=lane,
                action="approve",
                actor=actor,
                approved=True,
                expires_at=lane_state.get("expires_at"),
            )
        )

    if revoke:
        lane_state["approved"] = False
        lane_state["approved_by"] = None
        lane_state["approved_at"] = None
        lane_state["expires_at"] = None
        entries.append(
            _audit_entry(
                timestamp=timestamp,
                lane=lane,
                action="revoke",
                actor=actor,
                approved=False,
                expires_at=None,
            )
        )

    if expires_at is not None:
        lane_state["expires_at"] = expires_at
        entries.append(
            _audit_entry(
                timestamp=timestamp,
                lane=lane,
                action="set_expiry",
                actor=actor,
                approved=bool(lane_state.get("approved")),
                expires_at=expires_at,
            )
        )

    if clear_expiry:
        lane_state["expires_at"] = None
        entries.append(
            _audit_entry(
                timestamp=timestamp,
                lane=lane,
                action="clear_expiry",
                actor=actor,
                approved=bool(lane_state.get("approved")),
                expires_at=None,
            )
        )

    lanes[lane] = lane_state
    path = approval_state.write_approval_state(lanes, runtime_root=resolved_runtime_root)
    _append_audit_entries(_approval_actions_log_path(resolved_runtime_root), entries)
    return {
        "ok": True,
        "lane": lane,
        "actor": actor,
        "state_path": str(path),
        "state": lane_state,
        "audit_entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a controlled approval update for one remediation lane.")
    parser.add_argument("--lane", required=True, choices=approval_state.LANES)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--revoke", action="store_true")
    parser.add_argument("--expires-at")
    parser.add_argument("--clear-expiry", action="store_true")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        payload = write_approval_action(
            lane=args.lane,
            actor=args.actor,
            approve=args.approve,
            revoke=args.revoke,
            expires_at=args.expires_at,
            clear_expiry=args.clear_expiry,
        )
    except Exception as exc:
        error_payload = {"ok": False, "errors": [str(exc)]}
        stream = sys.stdout if args.json else sys.stderr
        print(json.dumps(error_payload, ensure_ascii=False, sort_keys=True), file=stream)
        return 1

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
