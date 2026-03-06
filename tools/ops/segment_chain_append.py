#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

GENESIS_PREV_CHAIN_HASH = "0" * 64
VALID_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _runtime_root(raw: str | None) -> Path:
    value = (raw or os.environ.get("LUKA_RUNTIME_ROOT", "")).strip()
    if not value:
        raise RuntimeError("runtime_root_missing")
    return Path(value).expanduser().resolve()


def _is_valid_segment_name(name: str) -> bool:
    if not name or name != Path(name).name:
        return False
    if "/" in name or "\\" in name or ".." in name:
        return False
    if name.startswith("~") or name.startswith("."):
        return False
    return True


def _is_hash64(value: str) -> bool:
    return bool(VALID_HEX_RE.match(value))


def _compute_chain_hash(
    *,
    segment_seq: int,
    segment_name: str,
    seal_hash: str,
    line_count: int,
    last_hash: str,
    prev_chain_hash: str,
) -> str:
    material = {
        "segment_seq": segment_seq,
        "segment_name": segment_name,
        "seal_hash": seal_hash,
        "line_count": line_count,
        "last_hash": last_hash,
        "prev_chain_hash": prev_chain_hash,
    }
    canonical = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid_chain_json:line={line_no}:{exc}") from exc
            if not isinstance(row, dict):
                raise RuntimeError(f"invalid_chain_row_type:line={line_no}")
            rows.append(row)
    return rows


def append_segment_chain(
    runtime_root: Path,
    *,
    segment_name: str,
    seal_hash: str,
    line_count: int,
    last_hash: str,
    segment_seq: int | None,
    prev_chain_hash: str | None,
) -> tuple[bool, dict[str, Any] | None, str | None]:
    if not _is_valid_segment_name(segment_name):
        return False, None, "invalid_segment_name"
    if line_count <= 0:
        return False, None, "invalid_line_count"
    if not _is_hash64(seal_hash):
        return False, None, "invalid_seal_hash"
    if not _is_hash64(last_hash):
        return False, None, "invalid_last_hash"
    if prev_chain_hash is not None and not _is_hash64(prev_chain_hash):
        return False, None, "invalid_prev_chain_hash"

    chain_path = runtime_root / "logs" / "segment_chain.jsonl"
    lock_path = chain_path.with_name(f"{chain_path.name}.lock")
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+", encoding="utf-8") as lock:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            entries = _load_entries(chain_path)
            seen_segments: set[str] = set()
            seen_seals: set[str] = set()
            for row in entries:
                seg = row.get("segment_name")
                sh = row.get("seal_hash")
                if isinstance(seg, str):
                    seen_segments.add(seg)
                if isinstance(sh, str):
                    seen_seals.add(sh)

            if segment_name in seen_segments:
                return False, None, "duplicate_segment"
            if seal_hash in seen_seals:
                return False, None, "duplicate_seal_hash"

            last = entries[-1] if entries else None
            expected_seq = 1
            expected_prev = GENESIS_PREV_CHAIN_HASH
            if isinstance(last, dict):
                try:
                    expected_seq = int(last.get("segment_seq")) + 1
                    expected_prev = str(last.get("chain_hash"))
                except Exception:
                    return False, None, "invalid_last_entry"
                if not _is_hash64(expected_prev):
                    return False, None, "invalid_last_chain_hash"

            incoming_seq = segment_seq if segment_seq is not None else expected_seq
            if incoming_seq != expected_seq:
                return False, None, "segment_seq_mismatch"

            incoming_prev = prev_chain_hash if prev_chain_hash is not None else expected_prev
            if incoming_prev != expected_prev:
                return False, None, "chain_fork_detected"

            chain_hash = _compute_chain_hash(
                segment_seq=incoming_seq,
                segment_name=segment_name,
                seal_hash=seal_hash,
                line_count=line_count,
                last_hash=last_hash,
                prev_chain_hash=incoming_prev,
            )
            record = {
                "segment_seq": incoming_seq,
                "segment_name": segment_name,
                "seal_hash": seal_hash,
                "line_count": line_count,
                "last_hash": last_hash,
                "prev_chain_hash": incoming_prev,
                "chain_hash": chain_hash,
                "ts_utc": _utc_now(),
            }
            with chain_path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                out.flush()
                os.fsync(out.fileno())
            return True, record, None
        finally:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one segment-chain entry.")
    parser.add_argument("--segment-name", required=True)
    parser.add_argument("--seal-hash", required=True)
    parser.add_argument("--line-count", required=True, type=int)
    parser.add_argument("--last-hash", required=True)
    parser.add_argument("--segment-seq", type=int, help="Optional explicit sequence (must be monotonic under lock)")
    parser.add_argument("--prev-chain-hash", help="Optional explicit prev hash (must match last chain hash)")
    parser.add_argument("--runtime-root", help="Override runtime root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        runtime_root = _runtime_root(args.runtime_root)
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"segment_chain_append_error:{exc}", file=sys.stderr)
        return 2

    ok, record, error = append_segment_chain(
        runtime_root,
        segment_name=args.segment_name,
        seal_hash=args.seal_hash,
        line_count=args.line_count,
        last_hash=args.last_hash,
        segment_seq=args.segment_seq,
        prev_chain_hash=args.prev_chain_hash,
    )
    if not ok:
        if args.json:
            print(json.dumps({"ok": False, "error": error}))
        else:
            print(f"segment_chain_append_error:{error}", file=sys.stderr)
        return 2

    assert record is not None
    if args.json:
        print(json.dumps({"ok": True, "path": str(runtime_root / "logs" / "segment_chain.jsonl"), "record": record}, ensure_ascii=False, separators=(",", ":")))
    else:
        print(
            "|".join(
                [
                    str(record["segment_seq"]),
                    str(record["prev_chain_hash"]),
                    str(record["chain_hash"]),
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
