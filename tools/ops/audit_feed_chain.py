#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ANCHOR_ACTION = "ledger_anchor"
GENESIS_PREV_HASH = "GENESIS"


def _default_feed_path() -> Path:
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", str(Path.home() / "0luka_runtime")).strip()
    return Path(runtime_root).expanduser() / "logs" / "activity_feed.jsonl"


def _compute_hash(entry: dict[str, Any]) -> str:
    payload = dict(entry)
    payload.pop("hash", None)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _scan_rotation_registry(registry_path: Path, *, log_name: str) -> tuple[list[dict[str, Any]], int]:
    if not registry_path.exists():
        return [], 0
    if not registry_path.is_file():
        return [{"line": 0, "error": f"rotation_registry_not_file:{registry_path}"}], 0

    errors: list[dict[str, Any]] = []
    seals_seen: set[str] = set()
    entries_checked = 0

    with registry_path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({"line": line_no, "error": "rotation_invalid_json", "detail": str(exc)})
                continue
            if not isinstance(entry, dict):
                errors.append({"line": line_no, "error": "rotation_non_object_json"})
                continue
            if entry.get("log") != log_name:
                continue
            action = entry.get("action")
            if action == "rotation_seal":
                entries_checked += 1
                seal_hash = entry.get("seal_hash")
                if not isinstance(seal_hash, str) or not seal_hash.strip():
                    errors.append({"line": line_no, "error": "rotation_seal_missing_hash"})
                    continue
                seals_seen.add(seal_hash)
            elif action == "rotation_continuation":
                entries_checked += 1
                prev_seal_hash = entry.get("prev_seal_hash")
                if not isinstance(prev_seal_hash, str) or not prev_seal_hash.strip():
                    errors.append({"line": line_no, "error": "rotation_continuation_missing_prev"})
                    continue
                if prev_seal_hash not in seals_seen:
                    errors.append(
                        {
                            "line": line_no,
                            "error": "rotation_continuation_prev_not_found",
                            "observed_prev_seal_hash": prev_seal_hash,
                        }
                    )
            else:
                continue

    return errors, entries_checked


def _audit(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "ok": False,
            "path": str(path),
            "lines_total": 0,
            "legacy_lines": 0,
            "hashed_lines": 0,
            "anchor_seen": False,
            "first_anchor_line": None,
            "last_hash": None,
            "errors": [{"line": 0, "error": f"missing_file:{path}"}],
        }
    if not path.is_file():
        return {
            "ok": False,
            "path": str(path),
            "lines_total": 0,
            "legacy_lines": 0,
            "hashed_lines": 0,
            "anchor_seen": False,
            "first_anchor_line": None,
            "last_hash": None,
            "errors": [{"line": 0, "error": f"not_a_file:{path}"}],
        }

    errors: list[dict[str, Any]] = []
    lines_total = 0
    legacy_lines = 0
    hashed_lines = 0
    anchor_seen = False
    first_anchor_line: int | None = None
    last_hash: str | None = None

    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            lines_total += 1
            line = raw.strip()
            if not line:
                if not anchor_seen:
                    legacy_lines += 1
                    continue
                errors.append({"line": line_no, "error": "empty_line_after_anchor"})
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                if not anchor_seen:
                    legacy_lines += 1
                    continue
                errors.append({"line": line_no, "error": "invalid_json", "detail": str(exc)})
                continue

            if not isinstance(entry, dict):
                if not anchor_seen:
                    legacy_lines += 1
                    continue
                errors.append({"line": line_no, "error": "non_object_json"})
                continue

            entry_hash = entry.get("hash")
            has_hash = isinstance(entry_hash, str) and bool(entry_hash.strip())

            if not anchor_seen:
                if not has_hash:
                    legacy_lines += 1
                    continue

                if entry.get("action") != ANCHOR_ACTION:
                    errors.append({"line": line_no, "error": "hashed_entry_before_anchor"})
                    continue
                if entry.get("prev_hash") != GENESIS_PREV_HASH:
                    errors.append({"line": line_no, "error": "anchor_prev_hash_mismatch"})
                    continue
                computed = _compute_hash(entry)
                if computed != entry_hash:
                    errors.append({"line": line_no, "error": "anchor_hash_mismatch", "computed": computed, "stored": entry_hash})
                    continue

                anchor_seen = True
                first_anchor_line = line_no
                hashed_lines += 1
                last_hash = entry_hash
                continue

            if not has_hash:
                errors.append({"line": line_no, "error": "unhashed_entry_after_anchor"})
                continue

            computed = _compute_hash(entry)
            if computed != entry_hash:
                errors.append({"line": line_no, "error": "hash_mismatch", "computed": computed, "stored": entry_hash})
                continue

            prev_hash = entry.get("prev_hash")
            if prev_hash != last_hash:
                errors.append({"line": line_no, "error": "prev_hash_mismatch", "expected": last_hash, "observed": prev_hash})
                continue

            hashed_lines += 1
            last_hash = entry_hash

    log_name = path.stem
    rotation_registry_path = path.parent / "rotation_registry.jsonl"
    rotation_errors, rotation_entries_checked = _scan_rotation_registry(rotation_registry_path, log_name=log_name)
    errors.extend(rotation_errors)

    ok = len(errors) == 0
    return {
        "ok": ok,
        "path": str(path),
        "lines_total": lines_total,
        "legacy_lines": legacy_lines,
        "hashed_lines": hashed_lines,
        "anchor_seen": anchor_seen,
        "first_anchor_line": first_anchor_line,
        "last_hash": last_hash,
        "rotation_registry_path": str(rotation_registry_path),
        "rotation_entries_checked": rotation_entries_checked,
        "errors": errors[:5],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit SHA-256 hash chain in runtime activity feed.")
    parser.add_argument("--path", type=Path, help="Path to activity_feed.jsonl")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    path = args.path if args.path else _default_feed_path()
    report = _audit(path)

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
