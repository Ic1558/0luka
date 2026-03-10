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

PROOF_VERSION = 1
SOURCE_NAME = "segment_chain.jsonl"
REQUIRED_LEAF_FIELDS = (
    "segment_seq",
    "segment_name",
    "seal_hash",
    "line_count",
    "last_hash",
    "prev_chain_hash",
    "chain_hash",
)


class SegmentChainError(RuntimeError):
    pass


class MerkleBuildError(RuntimeError):
    pass


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _runtime_root(raw: str | None = None) -> Path:
    value = (raw or os.environ.get("LUKA_RUNTIME_ROOT", "")).strip()
    if not value:
        raise RuntimeError("runtime_root_missing")
    return Path(value).expanduser().resolve()


def _logs_dir(runtime_root: Path) -> Path:
    return runtime_root / "logs"


def _ledger_root_path(logs_dir: Path) -> Path:
    return logs_dir / "ledger_root.json"


def _segment_chain_path(logs_dir: Path) -> Path:
    return logs_dir / SOURCE_NAME


def _epoch_manifest_path(logs_dir: Path) -> Path:
    return logs_dir / "epoch_manifest.jsonl"


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SegmentChainError(f"missing_segment_chain:{path}")
    if not path.is_file():
        raise SegmentChainError(f"segment_chain_not_file:{path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SegmentChainError(f"invalid_segment_chain_json:line={line_no}:{exc}") from exc
            if not isinstance(row, dict):
                raise SegmentChainError(f"segment_chain_non_object:line={line_no}")
            rows.append(row)

    if not rows:
        raise SegmentChainError("segment_chain_empty")
    return rows


def _validate_segment_chain_entries(entries: list[dict[str, Any]]) -> None:
    expected_seq = 1
    for index, entry in enumerate(entries, start=1):
        for field in REQUIRED_LEAF_FIELDS:
            if field not in entry:
                raise SegmentChainError(f"missing_field:{field}:line={index}")

        segment_seq = entry.get("segment_seq")
        segment_name = entry.get("segment_name")
        seal_hash = entry.get("seal_hash")
        line_count = entry.get("line_count")
        last_hash = entry.get("last_hash")
        prev_chain_hash = entry.get("prev_chain_hash")
        chain_hash = entry.get("chain_hash")

        if not isinstance(segment_seq, int):
            raise SegmentChainError(f"invalid_segment_seq:line={index}")
        if segment_seq != expected_seq:
            raise SegmentChainError(
                f"segment_seq_mismatch:line={index}:expected={expected_seq}:observed={segment_seq}"
            )
        if not isinstance(segment_name, str) or not segment_name:
            raise SegmentChainError(f"invalid_segment_name:line={index}")
        if not isinstance(seal_hash, str) or not seal_hash:
            raise SegmentChainError(f"invalid_seal_hash:line={index}")
        if not isinstance(line_count, int) or line_count <= 0:
            raise SegmentChainError(f"invalid_line_count:line={index}")
        if not isinstance(last_hash, str) or not last_hash:
            raise SegmentChainError(f"invalid_last_hash:line={index}")
        if not isinstance(prev_chain_hash, str):
            raise SegmentChainError(f"invalid_prev_chain_hash:line={index}")
        if not isinstance(chain_hash, str) or not chain_hash:
            raise SegmentChainError(f"invalid_chain_hash:line={index}")
        expected_seq += 1


def load_segment_chain_entries(logs_dir: Path) -> list[dict[str, Any]]:
    entries = _read_jsonl_objects(_segment_chain_path(logs_dir))
    _validate_segment_chain_entries(entries)
    return entries


def leaf_material(entry: dict[str, Any]) -> dict[str, Any]:
    return {field: entry[field] for field in REQUIRED_LEAF_FIELDS}


def compute_leaf_hash(entry: dict[str, Any]) -> str:
    return _sha256_text(_canonical_json(leaf_material(entry)))


def compute_leaf_hashes(entries: list[dict[str, Any]]) -> list[str]:
    return [compute_leaf_hash(entry) for entry in entries]


def compute_merkle_root(leaf_hashes: list[str]) -> str:
    if not leaf_hashes:
        raise MerkleBuildError("missing_leaves")

    level = list(leaf_hashes)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        next_level: list[str] = []
        for idx in range(0, len(level), 2):
            next_level.append(_sha256_text(level[idx] + level[idx + 1]))
        level = next_level
    return level[0]


def _read_last_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise MerkleBuildError(f"missing_epoch_manifest:{path}")
    if not path.is_file():
        raise MerkleBuildError(f"epoch_manifest_not_file:{path}")

    last: dict[str, Any] | None = None
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MerkleBuildError(f"invalid_epoch_manifest_json:line={line_no}:{exc}") from exc
            if not isinstance(row, dict):
                raise MerkleBuildError(f"epoch_manifest_non_object:line={line_no}")
            last = row

    if last is None:
        raise MerkleBuildError("epoch_manifest_empty")
    return last


def _extract_last_event_hash(log_heads: Any) -> str | None:
    if not isinstance(log_heads, dict):
        return None

    preferred = log_heads.get("activity_feed")
    if isinstance(preferred, dict):
        for key in ("last_event_hash", "last_line_hash", "tail_sha256"):
            value = preferred.get(key)
            if isinstance(value, str) and value:
                return value

    for head in log_heads.values():
        if not isinstance(head, dict):
            continue
        for key in ("last_event_hash", "last_line_hash", "tail_sha256"):
            value = head.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def load_epoch_anchor(logs_dir: Path) -> dict[str, Any]:
    record = _read_last_json_object(_epoch_manifest_path(logs_dir))
    epoch_id = record.get("epoch_id")
    if not isinstance(epoch_id, int):
        raise MerkleBuildError("invalid_epoch_anchor_epoch_id")
    return {
        "epoch_id": epoch_id,
        "last_event_hash": _extract_last_event_hash(record.get("log_heads")),
    }


def build_ledger_root_payload(logs_dir: Path, *, ts_utc: str | None = None) -> dict[str, Any]:
    entries = load_segment_chain_entries(logs_dir)
    leaf_hashes = compute_leaf_hashes(entries)
    merkle_root = compute_merkle_root(leaf_hashes)
    epoch_anchor = load_epoch_anchor(logs_dir)

    return {
        "version": PROOF_VERSION,
        "ts_utc": ts_utc or _utc_now(),
        "leaf_count": len(leaf_hashes),
        "segment_seq_min": entries[0]["segment_seq"],
        "segment_seq_max": entries[-1]["segment_seq"],
        "source": SOURCE_NAME,
        "segment_chain_head": entries[-1]["chain_hash"],
        "epoch_anchor": epoch_anchor,
        "merkle_root": merkle_root,
        "leaf_hashes": leaf_hashes,
    }


def write_ledger_root(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    serialized = _canonical_json(payload)
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic Merkle root over segment_chain.jsonl.")
    parser.add_argument("--runtime-root", help="Override runtime root")
    parser.add_argument("--dry-run", action="store_true", help="Compute payload without writing ledger_root.json")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    try:
        runtime_root = _runtime_root(args.runtime_root)
        logs_dir = _logs_dir(runtime_root)
        payload = build_ledger_root_payload(logs_dir)
        out_path = _ledger_root_path(logs_dir)
    except SegmentChainError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc), "exit_code": 2}, ensure_ascii=False))
        else:
            print(f"build_merkle_root_error:{exc}", file=sys.stderr)
        return 2
    except (MerkleBuildError, RuntimeError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc), "exit_code": 3}, ensure_ascii=False))
        else:
            print(f"build_merkle_root_error:{exc}", file=sys.stderr)
        return 3

    if not args.dry_run:
        try:
            write_ledger_root(out_path, payload)
        except Exception as exc:
            if args.json:
                print(
                    json.dumps(
                        {"ok": False, "error": f"write_failed:{exc}", "exit_code": 4, "path": str(out_path)},
                        ensure_ascii=False,
                    )
                )
            else:
                print(f"build_merkle_root_error:write_failed:{exc}", file=sys.stderr)
            return 4

    result = {
        "ok": True,
        "path": str(out_path),
        "dry_run": bool(args.dry_run),
        "ledger_root": payload,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"build_merkle_root:ok path={out_path} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
