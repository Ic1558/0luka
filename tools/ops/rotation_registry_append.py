#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _runtime_root(raw: str | None) -> Path:
    value = (raw or os.environ.get("LUKA_RUNTIME_ROOT", "")).strip()
    if not value:
        return (Path.home() / "0luka_runtime").resolve()
    return Path(value).expanduser().resolve()


def append_registry_record(
    registry_path: Path,
    *,
    segment_name: str,
    seal_hash: str,
    first_hash: str,
    last_hash: str,
    line_count: int,
    sealed_at_utc: str,
) -> dict[str, Any]:
    lock_path = registry_path.with_name(f"{registry_path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "segment_name": segment_name,
        "seal_hash": seal_hash,
        "first_hash": first_hash,
        "last_hash": last_hash,
        "line_count": line_count,
        "sealed_at_utc": sealed_at_utc,
        "registry_ts_utc": _utc_now(),
    }
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    with lock_path.open("a+", encoding="utf-8") as lock:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            with registry_path.open("a", encoding="utf-8") as out:
                out.write(payload + "\n")
                out.flush()
                os.fsync(out.fileno())
        finally:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one rotation registry entry.")
    parser.add_argument("segment_name")
    parser.add_argument("seal_hash")
    parser.add_argument("first_hash")
    parser.add_argument("last_hash")
    parser.add_argument("line_count", type=int)
    parser.add_argument("sealed_at_utc")
    parser.add_argument("--runtime-root", help="Override runtime root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    runtime_root = _runtime_root(args.runtime_root)
    registry_path = runtime_root / "logs" / "rotation_registry.jsonl"
    try:
        record = append_registry_record(
            registry_path,
            segment_name=args.segment_name,
            seal_hash=args.seal_hash,
            first_hash=args.first_hash,
            last_hash=args.last_hash,
            line_count=args.line_count,
            sealed_at_utc=args.sealed_at_utc,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": f"registry_append_failed:{exc}"}))
        else:
            print(f"rotation_registry_append_error: registry_append_failed:{exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {"ok": True, "path": str(registry_path), "record": record},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    else:
        print(f"rotation_registry_append_ok:{registry_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
