#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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

try:
    from core.config import RUNTIME_ROOT
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.config import RUNTIME_ROOT

RUNTIME_LOGS_DIR = RUNTIME_ROOT / "logs"
ROTATION_REGISTRY_PATH = RUNTIME_LOGS_DIR / "rotation_registry.jsonl"
TAIL_SCAN_BYTES = 131_072


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _resolve_log_path(log_name: str) -> Path:
    name = log_name.strip()
    if not name:
        raise ValueError("log_name_required")
    if name.endswith(".jsonl"):
        return RUNTIME_LOGS_DIR / name
    return RUNTIME_LOGS_DIR / f"{name}.jsonl"


def _read_last_nonempty_line(path: Path) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return ""
    with path.open("rb") as handle:
        pos = handle.seek(0, os.SEEK_END)
        buf = b""
        while pos > 0:
            step = 4096 if pos >= 4096 else pos
            pos -= step
            handle.seek(pos, os.SEEK_SET)
            buf = handle.read(step) + buf
            for raw in reversed(buf.splitlines()):
                if raw.strip():
                    return raw.decode("utf-8", errors="replace")
    return ""


def _decode_json_line(raw: bytes) -> dict[str, Any] | None:
    line = raw.decode("utf-8", errors="replace").strip()
    if not line:
        return None
    try:
        parsed = json.loads(line)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _scan_last_seal_hash_locked(handle: Any, log_name: str) -> str:
    handle.seek(0, os.SEEK_END)
    size = handle.tell()
    if size <= 0:
        return ""

    read_size = min(size, TAIL_SCAN_BYTES)
    start = size - read_size
    handle.seek(start, os.SEEK_SET)
    block = handle.read(read_size)
    if isinstance(block, str):
        block = block.encode("utf-8")

    if start > 0:
        nl = block.find(b"\n")
        if nl >= 0:
            block = block[nl + 1 :]
        else:
            block = b""

    for raw in reversed(block.splitlines()):
        parsed = _decode_json_line(raw)
        if not parsed:
            continue
        if parsed.get("action") != "rotation_seal":
            continue
        if parsed.get("log") != log_name:
            continue
        seal_hash = parsed.get("seal_hash")
        if isinstance(seal_hash, str) and seal_hash.strip():
            return seal_hash

    if start == 0:
        return ""

    handle.seek(0, os.SEEK_SET)
    found = ""
    for raw in handle:
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        parsed = _decode_json_line(raw)
        if not parsed:
            continue
        if parsed.get("action") != "rotation_seal":
            continue
        if parsed.get("log") != log_name:
            continue
        seal_hash = parsed.get("seal_hash")
        if isinstance(seal_hash, str) and seal_hash.strip():
            found = seal_hash
    return found


def _append_registry_entry_locked(handle: Any, entry: dict[str, Any]) -> None:
    handle.seek(0, os.SEEK_END)
    handle.write((json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8"))
    handle.flush()
    os.fsync(handle.fileno())


def write_rotation_seal(
    log_name: str,
    *,
    registry_path: Path = ROTATION_REGISTRY_PATH,
) -> dict[str, Any]:
    if fcntl is None:
        raise RuntimeError("flock_unavailable")

    log_path = _resolve_log_path(log_name)
    stat_size = int(log_path.stat().st_size) if log_path.exists() else 0
    tail_line = _read_last_nonempty_line(log_path)
    tail_sha256 = hashlib.sha256(tail_line.encode("utf-8")).hexdigest() if tail_line else ""

    payload = {
        "ts_utc": _utc_now(),
        "action": "rotation_seal",
        "log": log_name,
        "log_path": str(log_path),
        "size_bytes": stat_size,
        "tail_sha256": tail_sha256,
    }
    payload_canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["seal_hash"] = hashlib.sha256(payload_canonical.encode("utf-8")).hexdigest()

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            _append_registry_entry_locked(handle, payload)
            return payload
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_rotation_continuation(
    log_name: str,
    *,
    prev_seal_hash: str = "",
    registry_path: Path = ROTATION_REGISTRY_PATH,
) -> dict[str, Any]:
    if fcntl is None:
        raise RuntimeError("flock_unavailable")

    log_path = _resolve_log_path(log_name)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            resolved_prev = prev_seal_hash.strip() or _scan_last_seal_hash_locked(handle, log_name)
            payload = {
                "ts_utc": _utc_now(),
                "action": "rotation_continuation",
                "log": log_name,
                "log_path": str(log_path),
                "prev_seal_hash": resolved_prev,
            }
            payload_canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            payload["continuation_hash"] = hashlib.sha256(payload_canonical.encode("utf-8")).hexdigest()
            _append_registry_entry_locked(handle, payload)
            return payload
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Rotation continuity protocol writers.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    seal_p = sub.add_parser("seal", help="Write rotation_seal entry")
    seal_p.add_argument("--log", required=True, help="Log name, e.g. dispatcher")

    cont_p = sub.add_parser("continuation", help="Write rotation_continuation entry")
    cont_p.add_argument("--log", required=True, help="Log name, e.g. dispatcher")
    cont_p.add_argument("--prev-seal-hash", default="", help="Override previous seal hash")

    args = parser.parse_args()

    if args.cmd == "seal":
        row = write_rotation_seal(args.log)
    else:
        row = write_rotation_continuation(args.log, prev_seal_hash=args.prev_seal_hash)

    print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
