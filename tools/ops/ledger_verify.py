#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.audit_feed_segments import audit_segments
from tools.ops.audit_segment_chain import audit_segment_chain
from tools.ops.build_merkle_root import (
    MerkleBuildError,
    PROOF_VERSION,
    SegmentChainError,
    build_ledger_root_payload,
)

GENESIS_PREV_EPOCH_HASH = "0" * 64
LEGACY_GENESIS_PREV_EPOCH_HASH = "0" * 16


def _runtime_root(raw: str | None = None) -> Path:
    value = (raw or os.environ.get("LUKA_RUNTIME_ROOT", "")).strip()
    if not value:
        raise RuntimeError("runtime_root_missing")
    return Path(value).expanduser().resolve()


def _logs_dir(runtime_root: Path) -> Path:
    return runtime_root / "logs"


def _segment_chain_path(logs_dir: Path) -> Path:
    return logs_dir / "segment_chain.jsonl"


def _epoch_manifest_path(logs_dir: Path) -> Path:
    return logs_dir / "epoch_manifest.jsonl"


def _ledger_root_path(logs_dir: Path) -> Path:
    return logs_dir / "ledger_root.json"


def _sha256_text(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _compute_epoch_hash(epoch_id: int, prev_epoch_hash: str, log_heads: dict[str, Any]) -> str:
    material = str(epoch_id) + prev_epoch_hash + json.dumps(log_heads, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _compute_epoch_hash_legacy(epoch_id: int, prev_epoch_hash: str, log_heads: dict[str, Any]) -> str:
    material = str(epoch_id) + prev_epoch_hash + json.dumps(log_heads, sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _check_epoch_chain(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "ok": False,
            "path": str(path),
            "lines_total": 0,
            "epoch_lines": 0,
            "last_epoch_hash": None,
            "last_record": None,
            "errors": [{"error": "missing_epoch_manifest"}],
        }

    errors: list[dict[str, Any]] = []
    lines_total = 0
    epoch_lines = 0
    first_epoch_line: int | None = None
    prev_epoch_hash_expected = GENESIS_PREV_EPOCH_HASH
    last_epoch_hash: str | None = None
    last_record: dict[str, Any] | None = None

    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            lines_total += 1
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append({"line": line_no, "error": "invalid_json", "detail": str(exc)})
                continue
            if not isinstance(entry, dict):
                errors.append({"line": line_no, "error": "non_object_json"})
                continue

            epoch_id = entry.get("epoch_id")
            prev_epoch_hash = entry.get("prev_epoch_hash")
            log_heads = entry.get("log_heads")
            epoch_hash = entry.get("epoch_hash")

            if not isinstance(epoch_id, int):
                errors.append({"line": line_no, "error": "invalid_epoch_id"})
                continue
            if not isinstance(prev_epoch_hash, str):
                errors.append({"line": line_no, "error": "invalid_prev_epoch_hash"})
                continue
            if not isinstance(log_heads, dict):
                errors.append({"line": line_no, "error": "invalid_log_heads"})
                continue
            if not isinstance(epoch_hash, str):
                errors.append({"line": line_no, "error": "invalid_epoch_hash"})
                continue

            if first_epoch_line is None:
                first_epoch_line = line_no
                if prev_epoch_hash not in {GENESIS_PREV_EPOCH_HASH, LEGACY_GENESIS_PREV_EPOCH_HASH}:
                    errors.append({"line": line_no, "error": "genesis_chain_break", "observed": prev_epoch_hash})
            elif prev_epoch_hash != prev_epoch_hash_expected:
                errors.append(
                    {
                        "line": line_no,
                        "error": "epoch_chain_broken",
                        "expected": prev_epoch_hash_expected,
                        "observed": prev_epoch_hash,
                    }
                )

            computed = _compute_epoch_hash(epoch_id, prev_epoch_hash, log_heads)
            legacy_computed = _compute_epoch_hash_legacy(epoch_id, prev_epoch_hash, log_heads)
            if epoch_hash not in {computed, legacy_computed}:
                errors.append(
                    {
                        "line": line_no,
                        "error": "epoch_hash_mismatch",
                        "expected": computed,
                        "expected_legacy": legacy_computed,
                        "observed": epoch_hash,
                    }
                )

            epoch_lines += 1
            prev_epoch_hash_expected = epoch_hash
            last_epoch_hash = epoch_hash
            last_record = entry

    return {
        "ok": len(errors) == 0,
        "path": str(path),
        "lines_total": lines_total,
        "epoch_lines": epoch_lines,
        "last_epoch_hash": last_epoch_hash,
        "last_record": last_record,
        "errors": errors,
    }


def _check_epoch_head_match(runtime_root: Path, last_record: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not last_record:
        return []

    errors: list[dict[str, Any]] = []
    log_heads = last_record.get("log_heads", {})
    if not isinstance(log_heads, dict):
        return [{"error": "invalid_log_heads"}]

    for log_name, head_data in log_heads.items():
        if not isinstance(head_data, dict):
            errors.append({"error": "invalid_log_head", "log": log_name})
            continue
        rel_path = head_data.get("path")
        expected_hash = (
            head_data.get("last_event_hash")
            or head_data.get("last_line_hash")
            or head_data.get("tail_sha256")
        )
        expected_count = head_data.get("line_count")
        expected_offset = head_data.get("byte_offset")

        if not rel_path or not expected_hash:
            continue

        abs_path = runtime_root / rel_path
        if not abs_path.exists():
            errors.append({"error": "missing_registered_head", "log": log_name, "path": str(abs_path)})
            continue

        if not isinstance(expected_count, int):
            _ = _sha256_text(_read_last_nonempty_line(abs_path))
            continue

        expected_segment = head_data.get("segment")
        if expected_segment and expected_segment != rel_path:
            errors.append({"error": "segment_mismatch", "log": log_name, "expected": expected_segment, "actual": rel_path})
            continue

        line_at_expected = ""
        current_count = 0
        with abs_path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                if raw.strip():
                    current_count += 1
                    if current_count == expected_count:
                        line_at_expected = raw.strip()
                        break

        if current_count < expected_count:
            errors.append(
                {
                    "error": "ledger_truncated",
                    "path": rel_path,
                    "expected_line": expected_count,
                    "actual_line": current_count,
                }
            )
            continue

        hash_at_expected = _sha256_text(line_at_expected)
        if hash_at_expected != expected_hash:
            errors.append(
                {
                    "error": "epoch_head_mismatch",
                    "log": log_name,
                    "expected": expected_hash,
                    "actual": hash_at_expected,
                    "line_count": expected_count,
                }
            )
            continue

        if isinstance(expected_offset, int):
            actual_size = abs_path.stat().st_size
            if actual_size < expected_offset:
                errors.append(
                    {
                        "error": "epoch_head_offset_regression",
                        "log": log_name,
                        "expected_byte_offset": expected_offset,
                        "actual_byte_offset": actual_size,
                    }
                )

    return errors


def verify_epoch_manifest(runtime_root: Path) -> dict[str, Any]:
    report = _check_epoch_chain(_epoch_manifest_path(_logs_dir(runtime_root)))
    if report["ok"] and report.get("last_record"):
        head_errors = _check_epoch_head_match(runtime_root, report["last_record"])
        if head_errors:
            report["ok"] = False
            report["errors"].extend(head_errors)
    return report


def _load_ledger_root(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError("missing_ledger_root")
    if not path.is_file():
        raise RuntimeError("ledger_root_not_file")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid_ledger_root_json:{exc}") from exc
    if not isinstance(obj, dict):
        raise RuntimeError("ledger_root_non_object")
    return obj


def verify_ledger_root(runtime_root: Path) -> dict[str, Any]:
    logs_dir = _logs_dir(runtime_root)
    path = _ledger_root_path(logs_dir)
    errors: list[dict[str, Any]] = []
    stored: dict[str, Any] | None = None
    computed: dict[str, Any] | None = None

    try:
        stored = _load_ledger_root(path)
    except RuntimeError as exc:
        errors.append({"error": str(exc)})
        return {
            "ok": False,
            "path": str(path),
            "first_failure": errors[0]["error"],
            "errors": errors,
        }

    try:
        computed = build_ledger_root_payload(logs_dir, ts_utc=stored.get("ts_utc") if isinstance(stored.get("ts_utc"), str) else None)
    except SegmentChainError as exc:
        errors.append({"error": str(exc)})
    except (MerkleBuildError, RuntimeError) as exc:
        errors.append({"error": str(exc)})

    version = stored.get("version")
    if version != PROOF_VERSION:
        errors.append({"error": "ledger_root_version_mismatch", "expected": PROOF_VERSION, "observed": version})

    if computed is not None:
        if stored.get("source") != computed.get("source"):
            errors.append({"error": "source_mismatch", "expected": computed.get("source"), "observed": stored.get("source")})
        if stored.get("leaf_count") != computed.get("leaf_count"):
            errors.append(
                {
                    "error": "leaf_count_mismatch",
                    "expected": computed.get("leaf_count"),
                    "observed": stored.get("leaf_count"),
                }
            )
        if stored.get("segment_seq_min") != computed.get("segment_seq_min"):
            errors.append(
                {
                    "error": "segment_seq_min_mismatch",
                    "expected": computed.get("segment_seq_min"),
                    "observed": stored.get("segment_seq_min"),
                }
            )
        if stored.get("segment_seq_max") != computed.get("segment_seq_max"):
            errors.append(
                {
                    "error": "segment_seq_max_mismatch",
                    "expected": computed.get("segment_seq_max"),
                    "observed": stored.get("segment_seq_max"),
                }
            )
        if stored.get("merkle_root") != computed.get("merkle_root"):
            errors.append(
                {
                    "error": "merkle_root_mismatch",
                    "expected": computed.get("merkle_root"),
                    "observed": stored.get("merkle_root"),
                }
            )
        if stored.get("segment_chain_head") != computed.get("segment_chain_head"):
            errors.append(
                {
                    "error": "stale_segment_chain_head",
                    "expected": computed.get("segment_chain_head"),
                    "observed": stored.get("segment_chain_head"),
                }
            )
        if stored.get("epoch_anchor") != computed.get("epoch_anchor"):
            errors.append(
                {
                    "error": "stale_epoch_anchor",
                    "expected": computed.get("epoch_anchor"),
                    "observed": stored.get("epoch_anchor"),
                }
            )
        if stored.get("leaf_hashes") != computed.get("leaf_hashes"):
            errors.append({"error": "leaf_hashes_mismatch"})

    return {
        "ok": len(errors) == 0,
        "path": str(path),
        "first_failure": errors[0]["error"] if errors else None,
        "segment_chain_path": str(_segment_chain_path(logs_dir)),
        "stored_merkle_root": stored.get("merkle_root"),
        "computed_merkle_root": computed.get("merkle_root") if computed is not None else None,
        "stored_segment_chain_head": stored.get("segment_chain_head"),
        "computed_segment_chain_head": computed.get("segment_chain_head") if computed is not None else None,
        "stored_leaf_count": stored.get("leaf_count"),
        "computed_leaf_count": computed.get("leaf_count") if computed is not None else None,
        "errors": errors,
    }


def verify_ledger(runtime_root: Path) -> dict[str, Any]:
    logs_dir = _logs_dir(runtime_root)
    checks = {
        "segment_integrity": audit_segments(
            logs_dir,
            deep=False,
            enforce_seals=False,
            strict_discovery=False,
        ),
        "segment_chain": audit_segment_chain(logs_dir),
        "epoch_manifest": verify_epoch_manifest(runtime_root),
        "ledger_root": verify_ledger_root(runtime_root),
    }

    ordered_failures = [
        ("segment_integrity", checks["segment_integrity"]),
        ("segment_chain", checks["segment_chain"]),
        ("epoch_manifest", checks["epoch_manifest"]),
        ("ledger_root", checks["ledger_root"]),
    ]
    first_failure: str | None = None
    errors: list[dict[str, Any]] = []
    for name, report in ordered_failures:
        if bool(report.get("ok")):
            continue
        if first_failure is None:
            first_failure = name
        stage_errors = report.get("errors")
        if isinstance(stage_errors, list):
            for entry in stage_errors:
                if isinstance(entry, dict):
                    errors.append({"check": name, **entry})
                else:
                    errors.append({"check": name, "error": str(entry)})

    return {
        "ok": all(bool(report.get("ok")) for report in checks.values()),
        "runtime_root": str(runtime_root),
        "checks": checks,
        "first_failure": first_failure,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify segment integrity, epoch continuity, and Merkle ledger proof.")
    parser.add_argument("--runtime-root", help="Override runtime root")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    try:
        runtime_root = _runtime_root(args.runtime_root)
    except RuntimeError as exc:
        report = {
            "ok": False,
            "runtime_root": None,
            "checks": {
                "segment_integrity": {"ok": False, "errors": [{"error": str(exc)}]},
                "segment_chain": {"ok": False, "errors": [{"error": str(exc)}]},
                "epoch_manifest": {"ok": False, "errors": [{"error": str(exc)}]},
                "ledger_root": {"ok": False, "errors": [{"error": str(exc)}]},
            },
            "first_failure": "segment_integrity",
            "errors": [{"check": "segment_integrity", "error": str(exc)}],
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(f"ledger_verify:fail error={exc}", file=sys.stderr)
        return 2

    report = verify_ledger(runtime_root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        if report["ok"]:
            print(f"ledger_verify:ok runtime_root={runtime_root}")
        else:
            print(f"ledger_verify:fail runtime_root={runtime_root} first_failure={report['first_failure']}", file=sys.stderr)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
