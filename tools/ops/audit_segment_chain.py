#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

GENESIS_PREV_CHAIN_HASH = "0" * 64
ROTATED_SEGMENT_NAME_RE = re.compile(r"^activity_feed[._](\d{8}T\d{6}Z)\.jsonl$")


def _default_logs_dir() -> Path:
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", str(Path.home() / "0luka_runtime")).strip()
    return Path(runtime_root).expanduser() / "logs"


def _is_valid_segment_name(name: str) -> bool:
    if not name or name != Path(name).name:
        return False
    if "/" in name or "\\" in name or ".." in name:
        return False
    if name.startswith("~") or name.startswith("."):
        return False
    return True


def _compute_chain_hash(entry: dict[str, Any]) -> str:
    material = {
        "segment_seq": entry["segment_seq"],
        "segment_name": entry["segment_name"],
        "seal_hash": entry["seal_hash"],
        "line_count": entry["line_count"],
        "last_hash": entry["last_hash"],
        "prev_chain_hash": entry["prev_chain_hash"],
    }
    canonical = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if not path.exists():
        return rows, errors
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({"line": line_no, "error": "invalid_json", "detail": str(exc)})
                continue
            if not isinstance(row, dict):
                errors.append({"line": line_no, "error": "non_object_json"})
                continue
            rows.append(row)
    return rows, errors


def _load_registry(logs_dir: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
    registry_path = logs_dir / "rotation_registry.jsonl"
    rows, errors = _load_jsonl(registry_path)
    mapping: dict[str, str] = {}
    for idx, row in enumerate(rows, start=1):
        name = row.get("segment_name")
        seal = row.get("seal_hash")
        if isinstance(name, str) and isinstance(seal, str):
            mapping[name] = seal
        elif isinstance(name, str):
            # Has segment_name but seal_hash missing/malformed
            errors.append({"line": idx, "error": "invalid_registry_entry"})
        # else: legacy row without segment_name (pre-Phase-3.3) — skip silently
    return mapping, errors


def _present_segment_names(logs_dir: Path) -> set[str]:
    names: set[str] = set()
    archive_dir = logs_dir / "archive"
    if archive_dir.exists() and archive_dir.is_dir():
        for path in archive_dir.glob("activity_feed*.jsonl"):
            if not path.is_file():
                continue
            if ROTATED_SEGMENT_NAME_RE.match(path.name):
                names.add(path.name)
    active = logs_dir / "activity_feed.jsonl"
    if active.exists() and active.is_file():
        names.add(active.name)
    return names


def _segment_timestamp_epoch(name: str) -> int | None:
    match = ROTATED_SEGMENT_NAME_RE.match(name)
    if not match:
        return None
    token = match.group(1)
    try:
        parsed = time.strptime(token, "%Y%m%dT%H%M%SZ")
        return int(calendar.timegm(parsed))
    except ValueError:
        return None


def audit_segment_chain(logs_dir: Path) -> dict[str, Any]:
    chain_path = logs_dir / "segment_chain.jsonl"
    entries, errors = _load_jsonl(chain_path)
    if not chain_path.exists():
        return {
            "ok": True,
            "path": str(chain_path),
            "entries_total": 0,
            "first_failure": None,
            "warnings": [f"segment_chain_missing:{chain_path}"],
            "errors": [],
        }

    registry_map, registry_errors = _load_registry(logs_dir)
    errors.extend(registry_errors)
    present_names = _present_segment_names(logs_dir)
    present_timestamps = [
        ts for ts in (_segment_timestamp_epoch(name) for name in present_names) if ts is not None
    ]
    oldest_retained_ts = min(present_timestamps) if present_timestamps else None

    seen_segment_names: set[str] = set()
    seen_seal_hashes: set[str] = set()
    expected_seq = 1
    expected_prev = GENESIS_PREV_CHAIN_HASH
    max_seq = max((entry.get("segment_seq") for entry in entries if isinstance(entry.get("segment_seq"), int)), default=0)
    existence_checks = 0
    existence_skipped = 0

    for line_no, entry in enumerate(entries, start=1):
        segment_seq = entry.get("segment_seq")
        segment_name = entry.get("segment_name")
        seal_hash = entry.get("seal_hash")
        line_count = entry.get("line_count")
        last_hash = entry.get("last_hash")
        prev_chain_hash = entry.get("prev_chain_hash")
        chain_hash = entry.get("chain_hash")

        if not isinstance(segment_seq, int):
            errors.append({"line": line_no, "error": "invalid_segment_seq"})
            continue
        if not isinstance(segment_name, str) or not _is_valid_segment_name(segment_name):
            errors.append({"line": line_no, "error": "invalid_segment_name"})
            continue
        if not isinstance(seal_hash, str):
            errors.append({"line": line_no, "error": "invalid_seal_hash"})
            continue
        if not isinstance(line_count, int):
            errors.append({"line": line_no, "error": "invalid_line_count"})
            continue
        if not isinstance(last_hash, str):
            errors.append({"line": line_no, "error": "invalid_last_hash"})
            continue
        if not isinstance(prev_chain_hash, str):
            errors.append({"line": line_no, "error": "invalid_prev_chain_hash"})
            continue
        if not isinstance(chain_hash, str):
            errors.append({"line": line_no, "error": "invalid_chain_hash"})
            continue

        if segment_name in seen_segment_names:
            errors.append({"line": line_no, "error": "duplicate_segment", "segment_name": segment_name})
            continue
        if seal_hash in seen_seal_hashes:
            errors.append({"line": line_no, "error": "duplicate_seal_hash", "seal_hash": seal_hash})
            continue
        seen_segment_names.add(segment_name)
        seen_seal_hashes.add(seal_hash)

        if segment_seq != expected_seq:
            errors.append(
                {
                    "line": line_no,
                    "error": "segment_seq_mismatch",
                    "expected": expected_seq,
                    "observed": segment_seq,
                }
            )
            continue
        if prev_chain_hash != expected_prev:
            errors.append(
                {
                    "line": line_no,
                    "error": "chain_fork_detected",
                    "expected": expected_prev,
                    "observed": prev_chain_hash,
                }
            )
            continue

        computed = _compute_chain_hash(entry)
        if chain_hash != computed:
            errors.append({"line": line_no, "error": "chain_hash_mismatch", "expected": computed, "observed": chain_hash})
            continue

        mapped_seal = registry_map.get(segment_name)
        if mapped_seal is None:
            errors.append({"line": line_no, "error": "missing_registry_entry", "segment_name": segment_name})
            continue
        if mapped_seal != seal_hash:
            errors.append(
                {
                    "line": line_no,
                    "error": "registry_seal_mismatch",
                    "segment_name": segment_name,
                    "expected": mapped_seal,
                    "observed": seal_hash,
                }
            )
            continue

        # Advance continuity expectation once the chain row itself is valid.
        # File existence is checked separately with retention-aware policy.
        expected_seq = segment_seq + 1
        expected_prev = chain_hash

        # Retention-aware file check:
        # - Always check when segment name is currently present on disk.
        # - Otherwise, check only if entry timestamp is inside retained timestamp window.
        #   Older entries outside current on-disk retention are accepted as historical chain.
        segment_ts = _segment_timestamp_epoch(segment_name)
        should_check_existence = segment_name in present_names
        if not should_check_existence and oldest_retained_ts is not None and segment_ts is not None:
            if segment_ts >= oldest_retained_ts:
                should_check_existence = True
        if not should_check_existence and oldest_retained_ts is None and segment_seq == max_seq:
            # Safety fallback: if no retained files are visible, still check newest chain entry.
            should_check_existence = True

        if should_check_existence:
            existence_checks += 1
            archive_path = logs_dir / "archive" / segment_name
            active_path = logs_dir / segment_name
            if segment_name not in present_names and not archive_path.exists() and not active_path.exists():
                errors.append({"line": line_no, "error": "missing_segment_file", "segment_name": segment_name})
        else:
            existence_skipped += 1

    first_failure = errors[0]["error"] if errors else None
    return {
        "ok": len(errors) == 0,
        "path": str(chain_path),
        "entries_total": len(entries),
        "retained_segment_files": len(present_names),
        "retention_anchor_epoch": oldest_retained_ts,
        "existence_checks": existence_checks,
        "existence_skipped": existence_skipped,
        "first_failure": first_failure,
        "errors": errors[:50],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit multi-segment chain continuity.")
    parser.add_argument("--runtime-root", type=Path, help="Override runtime root")
    parser.add_argument("--logs-dir", type=Path, help="Override logs directory directly")
    parser.add_argument("--json", action="store_true", help="Emit compact JSON")
    args = parser.parse_args()

    logs_dir = args.logs_dir if args.logs_dir else ((args.runtime_root / "logs") if args.runtime_root else _default_logs_dir())
    report = audit_segment_chain(logs_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
