#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]


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


def _count_nonempty_lines(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def _sha256_text(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compute_epoch_hash(epoch_id: int, prev_epoch_hash: str, log_heads: dict[str, Any]) -> str:
    material = str(epoch_id) + prev_epoch_hash + json.dumps(log_heads, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--runtime-root", type=str)
    args = parser.parse_args()

    runtime_root_str = args.runtime_root or os.environ.get("LUKA_RUNTIME_ROOT")
    if not runtime_root_str:
        raise RuntimeError("LUKA_RUNTIME_ROOT_UNSET")
    runtime_root = Path(runtime_root_str).resolve()

    logs_dir = runtime_root / "logs"
    manifest_path = logs_dir / "epoch_manifest.jsonl"

    prev_epoch_id = 0
    prev_epoch_hash = "0" * 64

    if manifest_path.exists():
        last_line = _read_last_nonempty_line(manifest_path)
        if last_line:
            try:
                last_epoch = json.loads(last_line)
                prev_epoch_id = int(last_epoch["epoch_id"])
                prev_epoch_hash = str(last_epoch["epoch_hash"])
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                if args.json:
                    print(json.dumps({"ok": False, "error": f"malformed_manifest:{exc}"}))
                else:
                    print(f"ERROR: malformed_manifest:{exc}", file=sys.stderr)
                return 2

    log_heads: dict[str, Any] = {}
    logs_to_track = {
        "dispatcher": "logs/dispatcher.jsonl",
        "activity_feed": "logs/activity_feed.jsonl",
        "rotation_seals": "logs/rotation_seals.jsonl",
    }

    for key, rel_path in logs_to_track.items():
        abs_path = runtime_root / rel_path
        if abs_path.exists():
            last_line = _read_last_nonempty_line(abs_path)
            log_heads[key] = {
                "path": rel_path,
                "last_event_hash": _sha256_text(last_line),
                "line_count": _count_nonempty_lines(abs_path),
            }

    epoch_id = prev_epoch_id + 1
    epoch_hash = _compute_epoch_hash(epoch_id, prev_epoch_hash, log_heads)

    record = {
        "event": "epoch_marker",
        "epoch_id": epoch_id,
        "prev_epoch_hash": prev_epoch_hash,
        "log_heads": log_heads,
        "epoch_hash": epoch_hash,
        "ts_utc": _utc_now(),
    }

    if not args.dry_run:
        logs_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = logs_dir / f".{manifest_path.name}.tmp"
        
        # We need to append to the existing manifest, but safely.
        # Since we use os.replace, we first copy existing content if it exists.
        
        try:
            with manifest_path.open("a+b") as handle:
                if fcntl:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                
                # Write to tmp
                with tmp_path.open("w", encoding="utf-8") as tmp:
                    # If manifest exists, we should ideally just append. 
                    # But prompt says: "Atomic: write to .tmp then os.replace()"
                    # This implies we rewrite the whole file or we just append to a copy.
                    # Usually "write to .tmp then os.replace" is for overwriting.
                    # If we are appending, we read existing and write new.
                    if manifest_path.exists():
                        # Read all from manifest_path and write to tmp
                        # But handle is open in a+b, let's use a separate read handle or just read from this one if we seek to 0.
                        handle.seek(0)
                        tmp.write(handle.read().decode("utf-8"))
                    
                    tmp.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
                    tmp.flush()
                    os.fsync(tmp.fileno())
                
                os.replace(tmp_path, manifest_path)
                
                if fcntl:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            if args.json:
                print(json.dumps({"ok": False, "error": str(exc)}))
            else:
                print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.json:
        print(json.dumps({"ok": True, "epoch_id": epoch_id, "epoch_hash": epoch_hash, "record": record}))
    else:
        print(f"OK: epoch_id={epoch_id} hash={epoch_hash}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
