#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
QUEUE_STATES = {"queued", "running", "success", "failed", "blocked"}
ALLOWED_LANES = {
    "memory_recovery",
    "worker_recovery",
    "api_recovery",
    "redis_recovery",
}
ALLOWED_ACTIONS = {
    "restart_worker",
    "restart_api",
    "redis_reconnect",
    "recover_memory_index",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _queue_path(runtime_root: Path | None = None) -> Path:
    root = runtime_root or _runtime_root()
    return root / "state" / "remediation_queue.json"


def _empty_queue() -> dict[str, Any]:
    return {
        "ok": True,
        "queue": [],
        "last_id": 0,
        "updated_at": _utc_now(),
    }


def _load_queue(runtime_root: Path | None = None) -> dict[str, Any]:
    path = _queue_path(runtime_root)
    if not path.exists():
        return _empty_queue()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("queue_not_object")
    rows = payload.get("queue")
    if not isinstance(rows, list):
        raise RuntimeError("queue_rows_invalid")
    payload.setdefault("ok", True)
    payload.setdefault("last_id", 0)
    payload.setdefault("updated_at", _utc_now())
    return payload


def _write_queue(payload: dict[str, Any], runtime_root: Path | None = None) -> None:
    path = _queue_path(runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _next_id(last_id: int) -> tuple[str, int]:
    new_last = max(0, int(last_id)) + 1
    return f"rq_{new_last:06d}", new_last


def _validate_lane(lane: str) -> None:
    if lane not in ALLOWED_LANES:
        raise RuntimeError(f"invalid_lane:{lane}")


def _validate_action(action: str) -> None:
    if action not in ALLOWED_ACTIONS:
        raise RuntimeError(f"invalid_action:{action}")


def _validate_state(state: str) -> None:
    if state not in QUEUE_STATES:
        raise RuntimeError(f"invalid_state:{state}")


def list_queue(*, runtime_root: Path | None = None) -> dict[str, Any]:
    payload = _load_queue(runtime_root)
    rows = payload.get("queue", [])
    return {
        "ok": True,
        "items": rows,
        "total": len(rows),
        "updated_at": payload.get("updated_at"),
    }


def enqueue_item(*, lane: str, action: str, runtime_root: Path | None = None) -> dict[str, Any]:
    _validate_lane(lane)
    _validate_action(action)
    payload = _load_queue(runtime_root)
    item_id, last_id = _next_id(int(payload.get("last_id", 0)))
    item = {
        "id": item_id,
        "lane": lane,
        "action": action,
        "state": "queued",
        "created_at": _utc_now(),
        "attempts": 0,
    }
    rows = payload.get("queue", [])
    rows.append(item)
    payload["queue"] = rows
    payload["last_id"] = last_id
    payload["updated_at"] = _utc_now()
    _write_queue(payload, runtime_root)
    return {"ok": True, "item": item}


def transition_item(
    *,
    item_id: str,
    state: str,
    attempts: int | None = None,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    _validate_state(state)
    payload = _load_queue(runtime_root)
    rows = payload.get("queue", [])
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("id") != item_id:
            continue
        row["state"] = state
        if attempts is not None:
            row["attempts"] = max(0, int(attempts))
        elif state in {"running", "failed"}:
            row["attempts"] = int(row.get("attempts", 0)) + 1
        row["updated_at"] = _utc_now()
        payload["updated_at"] = _utc_now()
        _write_queue(payload, runtime_root)
        return {"ok": True, "item": row}
    raise RuntimeError(f"queue_item_not_found:{item_id}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="0luka remediation queue")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    parser.add_argument("--enqueue", action="store_true", help="enqueue remediation item")
    parser.add_argument("--lane", type=str, default="", help="lane name")
    parser.add_argument("--action", type=str, default="", help="action name")
    parser.add_argument("--transition", action="store_true", help="transition queue item")
    parser.add_argument("--id", type=str, default="", help="queue item id")
    parser.add_argument("--state", type=str, default="", help="target queue state")
    parser.add_argument("--attempts", type=int, default=None, help="set attempts count")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        if args.enqueue:
            if not args.lane or not args.action:
                raise RuntimeError("enqueue_requires_lane_and_action")
            payload = enqueue_item(lane=args.lane, action=args.action)
        elif args.transition:
            if not args.id or not args.state:
                raise RuntimeError("transition_requires_id_and_state")
            payload = transition_item(item_id=args.id, state=args.state, attempts=args.attempts)
        else:
            payload = list_queue()
    except Exception as exc:
        payload = {"ok": False, "errors": [str(exc)]}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
