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
    from core.config import DISPATCH_LOG, RUNTIME_ROOT
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.config import DISPATCH_LOG, RUNTIME_ROOT

EPOCH_MANIFEST_PATH = RUNTIME_ROOT / "logs" / "epoch_manifest.jsonl"
GENESIS_PREV_EPOCH_HASH = "0000000000000000"
TAIL_SCAN_BYTES = 131_072


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def _read_last_epoch_entry_locked(handle: Any) -> dict[str, Any] | None:
    handle.seek(0, os.SEEK_END)
    size = handle.tell()
    if size <= 0:
        return None

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

    lines = block.splitlines()
    for raw in reversed(lines):
        parsed = _decode_json_line(raw)
        if not parsed:
            continue
        epoch_hash = parsed.get("epoch_hash")
        if isinstance(epoch_hash, str) and epoch_hash.strip():
            return parsed

    if start == 0:
        return None

    handle.seek(0, os.SEEK_SET)
    found: dict[str, Any] | None = None
    for raw in handle:
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        parsed = _decode_json_line(raw)
        if not parsed:
            continue
        epoch_hash = parsed.get("epoch_hash")
        if isinstance(epoch_hash, str) and epoch_hash.strip():
            found = parsed
    return found


def _snapshot_dispatcher_log_head(dispatcher_log_path: Path) -> dict[str, Any]:
    if not dispatcher_log_path.exists():
        return {
            "dispatcher": {
                "path": str(dispatcher_log_path),
                "exists": False,
                "size_bytes": 0,
                "tail_sha256": "",
            }
        }

    stat = dispatcher_log_path.stat()
    tail_line = _read_last_nonempty_line(dispatcher_log_path)
    tail_sha = hashlib.sha256(tail_line.encode("utf-8")).hexdigest() if tail_line else ""
    return {
        "dispatcher": {
            "path": str(dispatcher_log_path),
            "exists": True,
            "size_bytes": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "tail_sha256": tail_sha,
        }
    }


def compute_epoch_hash(epoch_id: int, prev_epoch_hash: str, log_heads: dict[str, Any]) -> str:
    canonical = str(epoch_id) + prev_epoch_hash + json.dumps(log_heads, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_epoch_marker(
    epoch_id: int,
    *,
    dispatcher_log_path: Path = DISPATCH_LOG,
    manifest_path: Path = EPOCH_MANIFEST_PATH,
) -> dict[str, Any]:
    if fcntl is None:
        raise RuntimeError("flock_unavailable")
    if epoch_id < 1:
        raise ValueError("epoch_id_must_be_positive")

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            last = _read_last_epoch_entry_locked(handle)
            prev_epoch_hash = GENESIS_PREV_EPOCH_HASH
            if last:
                last_hash = last.get("epoch_hash")
                if isinstance(last_hash, str) and last_hash.strip():
                    prev_epoch_hash = last_hash

            log_heads = _snapshot_dispatcher_log_head(dispatcher_log_path)
            epoch_hash = compute_epoch_hash(epoch_id, prev_epoch_hash, log_heads)
            entry = {
                "ts_utc": _utc_now(),
                "epoch_id": int(epoch_id),
                "prev_epoch_hash": prev_epoch_hash,
                "log_heads": log_heads,
                "epoch_hash": epoch_hash,
            }
            handle.seek(0, os.SEEK_END)
            handle.write((json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
            return entry
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def emit_epoch_marker_safe(
    epoch_id: int,
    *,
    dispatcher_log_path: Path = DISPATCH_LOG,
    manifest_path: Path = EPOCH_MANIFEST_PATH,
) -> dict[str, Any] | None:
    try:
        return append_epoch_marker(
            epoch_id,
            dispatcher_log_path=dispatcher_log_path,
            manifest_path=manifest_path,
        )
    except Exception:
        return None


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Append a dispatcher epoch marker.")
    parser.add_argument("--epoch-id", type=int, required=True, help="Epoch id to append")
    parser.add_argument("--manifest-path", type=Path, default=EPOCH_MANIFEST_PATH)
    parser.add_argument("--dispatcher-log-path", type=Path, default=DISPATCH_LOG)
    args = parser.parse_args()

    row = append_epoch_marker(
        args.epoch_id,
        dispatcher_log_path=args.dispatcher_log_path,
        manifest_path=args.manifest_path,
    )
    print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
