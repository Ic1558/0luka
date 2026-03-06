#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.build_merkle_root import (
    MerkleBuildError,
    PROOF_VERSION,
    SegmentChainError,
    build_ledger_root_payload,
)

EXPORT_VERSION = 1
REQUIRED_RELATIVE_FILES = (
    "logs/ledger_root.json",
    "logs/segment_chain.jsonl",
    "logs/epoch_manifest.jsonl",
    "logs/rotation_registry.jsonl",
    "logs/rotation_seals.jsonl",
    "export_manifest.json",
    "checksums.sha256",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError(f"json_not_object:{path}")
    return obj


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise RuntimeError(f"jsonl_non_object:{path}:line={line_no}")
            rows.append(row)
    return rows


def _parse_checksums(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            parts = line.split("  ", 1)
            if len(parts) != 2:
                raise RuntimeError(f"invalid_checksum_line:{line_no}")
            sha, rel = parts
            mapping[rel] = sha
    return mapping


def _verify_checksums(export_dir: Path) -> dict[str, Any]:
    path = export_dir / "checksums.sha256"
    rows = _parse_checksums(path)
    errors: list[dict[str, Any]] = []

    expected_paths = sorted(
        [
            str(item.relative_to(export_dir))
            for item in export_dir.rglob("*")
            if item.is_file() and item.name != "checksums.sha256"
        ]
    )
    if sorted(rows) != expected_paths:
        errors.append(
            {
                "error": "checksum_file_set_mismatch",
                "expected": expected_paths,
                "observed": sorted(rows),
            }
        )

    for rel, sha in rows.items():
        target = export_dir / rel
        if not target.exists():
            errors.append({"error": "checksum_target_missing", "path": rel})
            continue
        observed = _sha256_file(target)
        if observed != sha:
            errors.append({"error": "checksum_mismatch", "path": rel, "expected": sha, "observed": observed})

    return {
        "ok": len(errors) == 0,
        "path": str(path),
        "first_failure": errors[0]["error"] if errors else None,
        "errors": errors,
    }


def _compute_epoch_hash(epoch_id: int, prev_epoch_hash: str, log_heads: dict[str, Any]) -> str:
    material = str(epoch_id) + prev_epoch_hash + json.dumps(log_heads, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _compute_epoch_hash_legacy(epoch_id: int, prev_epoch_hash: str, log_heads: dict[str, Any]) -> str:
    material = str(epoch_id) + prev_epoch_hash + json.dumps(log_heads, sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _verify_epoch_manifest(export_dir: Path, ledger_root: dict[str, Any]) -> dict[str, Any]:
    path = export_dir / "logs" / "epoch_manifest.jsonl"
    rows = _load_jsonl(path)
    errors: list[dict[str, Any]] = []
    prev_expected = "0" * 64
    last_row: dict[str, Any] | None = None

    for index, row in enumerate(rows, start=1):
        epoch_id = row.get("epoch_id")
        prev_epoch_hash = row.get("prev_epoch_hash")
        epoch_hash = row.get("epoch_hash")
        log_heads = row.get("log_heads")

        if not isinstance(epoch_id, int):
            errors.append({"error": "invalid_epoch_id", "line": index})
            continue
        if not isinstance(prev_epoch_hash, str):
            errors.append({"error": "invalid_prev_epoch_hash", "line": index})
            continue
        if not isinstance(epoch_hash, str):
            errors.append({"error": "invalid_epoch_hash", "line": index})
            continue
        if not isinstance(log_heads, dict):
            errors.append({"error": "invalid_log_heads", "line": index})
            continue

        if index == 1:
            if prev_epoch_hash not in {"0" * 64, "0" * 16}:
                errors.append({"error": "genesis_chain_break", "line": index})
        elif prev_epoch_hash != prev_expected:
            errors.append(
                {"error": "epoch_chain_broken", "line": index, "expected": prev_expected, "observed": prev_epoch_hash}
            )

        expected = _compute_epoch_hash(epoch_id, prev_epoch_hash, log_heads)
        legacy = _compute_epoch_hash_legacy(epoch_id, prev_epoch_hash, log_heads)
        if epoch_hash not in {expected, legacy}:
            errors.append({"error": "epoch_hash_mismatch", "line": index})
            continue

        prev_expected = epoch_hash
        last_row = row

    anchor = ledger_root.get("epoch_anchor")
    if isinstance(last_row, dict) and isinstance(anchor, dict):
        if last_row.get("epoch_id") != anchor.get("epoch_id"):
            errors.append(
                {
                    "error": "epoch_anchor_epoch_id_mismatch",
                    "expected": last_row.get("epoch_id"),
                    "observed": anchor.get("epoch_id"),
                }
            )
        last_hash = None
        log_heads = last_row.get("log_heads")
        if isinstance(log_heads, dict):
            feed_head = log_heads.get("activity_feed")
            if isinstance(feed_head, dict):
                candidate = feed_head.get("last_event_hash")
                if isinstance(candidate, str):
                    last_hash = candidate
        if last_hash != anchor.get("last_event_hash"):
            errors.append(
                {
                    "error": "epoch_anchor_last_event_hash_mismatch",
                    "expected": last_hash,
                    "observed": anchor.get("last_event_hash"),
                }
            )

    return {
        "ok": len(errors) == 0,
        "path": str(path),
        "epoch_lines": len(rows),
        "first_failure": errors[0]["error"] if errors else None,
        "errors": errors,
    }


def _verify_registry_seals(export_dir: Path) -> dict[str, Any]:
    registry_rows = _load_jsonl(export_dir / "logs" / "rotation_registry.jsonl")
    seal_rows = _load_jsonl(export_dir / "logs" / "rotation_seals.jsonl")
    chain_rows = _load_jsonl(export_dir / "logs" / "segment_chain.jsonl")
    errors: list[dict[str, Any]] = []

    registry_map: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(registry_rows, start=1):
        name = row.get("segment_name")
        seal_hash = row.get("seal_hash")
        if name is None:
            continue
        if not isinstance(name, str) or not isinstance(seal_hash, str):
            errors.append({"error": "invalid_registry_entry", "line": index})
            continue
        if name in registry_map:
            errors.append({"error": "duplicate_registry_segment", "segment_name": name})
            continue
        registry_map[name] = row

    seal_map: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(seal_rows, start=1):
        name = row.get("segment_name")
        seal_hash = row.get("seal_hash")
        if not isinstance(name, str) or not isinstance(seal_hash, str):
            errors.append({"error": "invalid_seal_entry", "line": index})
            continue
        if name in seal_map:
            errors.append({"error": "duplicate_seal_segment", "segment_name": name})
            continue
        seal_map[name] = row

    for row in chain_rows:
        name = row.get("segment_name")
        seal_hash = row.get("seal_hash")
        line_count = row.get("line_count")
        last_hash = row.get("last_hash")
        registry = registry_map.get(name) if isinstance(name, str) else None
        seal = seal_map.get(name) if isinstance(name, str) else None

        if registry is None:
            errors.append({"error": "missing_registry_entry", "segment_name": name})
            continue
        if registry.get("seal_hash") != seal_hash:
            errors.append({"error": "registry_seal_mismatch", "segment_name": name})
        if seal is None:
            errors.append({"error": "missing_seal_entry", "segment_name": name})
            continue
        if seal.get("seal_hash") != seal_hash:
            errors.append({"error": "seal_hash_mismatch", "segment_name": name})
        if seal.get("line_count") != line_count:
            errors.append({"error": "seal_line_count_mismatch", "segment_name": name})
        if seal.get("last_hash") != last_hash:
            errors.append({"error": "seal_last_hash_mismatch", "segment_name": name})

    return {
        "ok": len(errors) == 0,
        "first_failure": errors[0]["error"] if errors else None,
        "errors": errors,
    }


def verify_exported_proof(export_dir: Path) -> dict[str, Any]:
    export_dir = export_dir.expanduser().resolve()
    errors: list[dict[str, Any]] = []
    checks: dict[str, dict[str, Any]] = {}

    if not export_dir.exists() or not export_dir.is_dir():
        return {
            "ok": False,
            "checks": {},
            "first_failure": "missing_export_dir",
            "errors": [{"error": "missing_export_dir", "path": str(export_dir)}],
        }

    missing = [rel for rel in REQUIRED_RELATIVE_FILES if not (export_dir / rel).exists()]
    if missing:
        return {
            "ok": False,
            "checks": {},
            "first_failure": "missing_required_file",
            "errors": [{"error": "missing_required_file", "paths": missing}],
        }

    try:
        export_manifest = _read_json(export_dir / "export_manifest.json")
        ledger_root = _read_json(export_dir / "logs" / "ledger_root.json")
    except Exception as exc:
        return {
            "ok": False,
            "checks": {},
            "first_failure": "invalid_export_metadata",
            "errors": [{"error": f"invalid_export_metadata:{exc}"}],
        }

    checks["checksums"] = _verify_checksums(export_dir)
    checks["registry_seals"] = _verify_registry_seals(export_dir)
    checks["epoch_manifest"] = _verify_epoch_manifest(export_dir, ledger_root)

    try:
        computed = build_ledger_root_payload(export_dir / "logs", ts_utc=ledger_root.get("ts_utc"))
        ledger_errors: list[dict[str, Any]] = []
        if ledger_root.get("version") != PROOF_VERSION:
            ledger_errors.append({"error": "ledger_root_version_mismatch"})
        if export_manifest.get("version") != EXPORT_VERSION:
            ledger_errors.append({"error": "export_manifest_version_mismatch"})
        if computed.get("merkle_root") != ledger_root.get("merkle_root"):
            ledger_errors.append(
                {
                    "error": "merkle_root_mismatch",
                    "expected": computed.get("merkle_root"),
                    "observed": ledger_root.get("merkle_root"),
                }
            )
        if computed.get("segment_chain_head") != ledger_root.get("segment_chain_head"):
            ledger_errors.append(
                {
                    "error": "stale_segment_chain_head",
                    "expected": computed.get("segment_chain_head"),
                    "observed": ledger_root.get("segment_chain_head"),
                }
            )
        if computed.get("epoch_anchor") != ledger_root.get("epoch_anchor"):
            ledger_errors.append({"error": "epoch_anchor_mismatch"})
        checks["segment_chain"] = {
            "ok": True,
            "entries_total": computed.get("leaf_count"),
            "first_failure": None,
            "errors": [],
        }
        checks["ledger_root"] = {
            "ok": len(ledger_errors) == 0,
            "first_failure": ledger_errors[0]["error"] if ledger_errors else None,
            "stored_merkle_root": ledger_root.get("merkle_root"),
            "computed_merkle_root": computed.get("merkle_root"),
            "errors": ledger_errors,
        }
    except SegmentChainError as exc:
        checks["segment_chain"] = {"ok": False, "first_failure": str(exc), "errors": [{"error": str(exc)}]}
        checks["ledger_root"] = {"ok": False, "first_failure": str(exc), "errors": [{"error": str(exc)}]}
    except (MerkleBuildError, RuntimeError) as exc:
        checks["segment_chain"] = {"ok": False, "first_failure": str(exc), "errors": [{"error": str(exc)}]}
        checks["ledger_root"] = {"ok": False, "first_failure": str(exc), "errors": [{"error": str(exc)}]}

    ok = all(bool(report.get("ok")) for report in checks.values())
    first_failure = None
    for name in ("checksums", "segment_chain", "epoch_manifest", "ledger_root", "registry_seals"):
        report = checks.get(name)
        if isinstance(report, dict) and not bool(report.get("ok")):
            first_failure = name
            break

    for name, report in checks.items():
        stage_errors = report.get("errors")
        if isinstance(stage_errors, list):
            for entry in stage_errors:
                if isinstance(entry, dict):
                    errors.append({"check": name, **entry})
                else:
                    errors.append({"check": name, "error": str(entry)})

    return {
        "ok": ok,
        "checks": checks,
        "first_failure": first_failure,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an exported ledger proof pack without live runtime state.")
    parser.add_argument("--path", type=Path, required=True, help="Export directory path")
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    args = parser.parse_args()

    report = verify_exported_proof(args.path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
