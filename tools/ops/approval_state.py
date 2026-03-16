#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
EXPIRING_SOON_SECONDS = 15 * 60
LANES = (
    "memory_recovery",
    "worker_recovery",
    "api_recovery",
    "redis_recovery",
    "task_execution",
)


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def approval_state_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / "approval_state.json"


def _default_entry() -> dict[str, Any]:
    return {
        "approved": False,
        "approved_by": None,
        "approved_at": None,
        "expires_at": None,
    }


def _decorate_entry(entry: dict[str, Any], *, valid: bool, validation_error: str | None, now: datetime) -> dict[str, Any]:
    expires_at = entry.get("expires_at")
    expires_dt = _parse_timestamp_dt(expires_at) if isinstance(expires_at, str) else None
    expired = bool(expires_dt is not None and expires_dt <= now)
    expiring_soon = bool(expires_dt is not None and not expired and expires_dt <= now + timedelta(seconds=EXPIRING_SOON_SECONDS))
    approved = bool(entry.get("approved"))
    return {
        **entry,
        "valid": valid,
        "validation_error": validation_error,
        "approval_present": approved,
        "approved_effective": approved and not expired and valid,
        "expired": expired,
        "expiring_soon": expiring_soon,
    }


def default_state() -> dict[str, Any]:
    return {lane: _default_entry() for lane in LANES}


def validate_lane(lane: str) -> str:
    if lane not in LANES:
        raise RuntimeError(f"approval_state_invalid:unsupported_lane:{lane}")
    return lane


def parse_timestamp(raw: Any, *, field: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise RuntimeError(f"approval_state_invalid:{field}_not_string")
    try:
        datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise RuntimeError(f"approval_state_invalid:{field}_bad_timestamp") from exc
    return raw


def _parse_timestamp_dt(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _normalize_entry(raw: Any, *, lane: str) -> dict[str, Any]:
    if raw is None:
        return _default_entry()
    if not isinstance(raw, dict):
        raise RuntimeError(f"approval_state_invalid:{lane}_not_object")
    approved = raw.get("approved", False)
    if not isinstance(approved, bool):
        raise RuntimeError(f"approval_state_invalid:{lane}_approved_not_bool")
    approved_by = raw.get("approved_by")
    if approved_by is not None and not isinstance(approved_by, str):
        raise RuntimeError(f"approval_state_invalid:{lane}_approved_by_not_string")
    approved_at = parse_timestamp(raw.get("approved_at"), field=f"{lane}_approved_at")
    expires_at = parse_timestamp(raw.get("expires_at"), field=f"{lane}_expires_at")
    return {
        "approved": approved,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "expires_at": expires_at,
    }


def load_approval_state(*, runtime_root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    resolved_runtime_root = runtime_root or _runtime_root()
    path = approval_state_path(resolved_runtime_root)
    now = now or datetime.now(timezone.utc)
    state = {
        "path": str(path),
        "exists": path.exists(),
        "lanes": {lane: _decorate_entry(_default_entry(), valid=True, validation_error=None, now=now) for lane in LANES},
    }
    if not path.exists():
        return state

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("approval_state_invalid:not_object")
    for lane in LANES:
        try:
            normalized = _normalize_entry(payload.get(lane), lane=lane)
            state["lanes"][lane] = _decorate_entry(normalized, valid=True, validation_error=None, now=now)
        except RuntimeError as exc:
            state["lanes"][lane] = _decorate_entry(_default_entry(), valid=False, validation_error=str(exc), now=now)
    return state


def write_approval_state(lanes: dict[str, Any], *, runtime_root: Path | None = None) -> Path:
    resolved_runtime_root = runtime_root or _runtime_root()
    path = approval_state_path(resolved_runtime_root)
    normalized = default_state()
    for lane in LANES:
        normalized[lane] = _normalize_entry(lanes.get(lane), lane=lane)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Read and validate the unified approval state.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    try:
        payload = load_approval_state()
    except Exception as exc:
        error_payload = {"ok": False, "errors": [str(exc)]}
        print(json.dumps(error_payload, ensure_ascii=False, sort_keys=True))
        return 1

    if args.json:
        print(json.dumps({"ok": True, **payload}, ensure_ascii=False, sort_keys=True))
        return 0

    print(f"approval_state: {payload['path']}")
    print(f"exists: {payload['exists']}")
    for lane in LANES:
        entry = payload["lanes"][lane]
        print(
            f"{lane}: approved={entry['approved']} approved_by={entry['approved_by'] or 'n/a'} "
            f"expires_at={entry['expires_at'] or 'n/a'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
