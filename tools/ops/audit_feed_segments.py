#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROTATED_SEGMENT_NAME_RE = re.compile(r"^activity_feed[._](\d{8}T\d{6}Z)\.jsonl$")
ERROR_TYPES = {
    "SEGMENT_GAP",
    "HASH_CHAIN_BREAK",
    "SEAL_MISSING",
    "SEAL_HASH_MISMATCH",
    "LINE_COUNT_MISMATCH",
    "SEGMENT_ORDER_INVALID",
}


@dataclass(frozen=True)
class Segment:
    path: Path
    name: str
    is_active: bool
    ts_token: str | None


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _default_logs_dir() -> Path:
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", str(Path.home() / "0luka_runtime")).strip()
    return Path(runtime_root).expanduser() / "logs"


def _extract_ts_token(name: str) -> str | None:
    match = ROTATED_SEGMENT_NAME_RE.match(name)
    return match.group(1) if match else None


def _canonical_entry_hash(entry: dict[str, Any]) -> str:
    payload = dict(entry)
    payload.pop("hash", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _err(error_type: str, *, segment: str, line: int | None = None, detail: str | None = None) -> dict[str, Any]:
    if error_type not in ERROR_TYPES:
        raise ValueError(f"unknown_error_type:{error_type}")
    out: dict[str, Any] = {"type": error_type, "segment": segment}
    if line is not None:
        out["line"] = line
    if detail:
        out["detail"] = detail
    return out


def _discover_segments(logs_dir: Path, *, strict_discovery: bool) -> tuple[list[Segment], list[dict[str, Any]], list[str]]:
    errors: list[dict[str, Any]] = []
    segments: list[Segment] = []
    ignored_files: list[str] = []
    active_path = logs_dir / "activity_feed.jsonl"
    archive_dir = logs_dir / "archive"

    if active_path.exists() and active_path.is_file():
        segments.append(Segment(path=active_path, name=active_path.name, is_active=True, ts_token=None))
    else:
        errors.append(_err("SEGMENT_GAP", segment=active_path.name, detail="missing_active_segment"))

    rotated: list[Segment] = []
    if archive_dir.exists() and archive_dir.is_dir():
        for path in sorted(archive_dir.glob("activity_feed*.jsonl")):
            name = path.name
            ts_token = _extract_ts_token(name)
            if ts_token is None:
                ignored_files.append(name)
                if strict_discovery:
                    errors.append(_err("SEGMENT_ORDER_INVALID", segment=name, detail="missing_or_invalid_timestamp_token"))
                continue
            rotated.append(Segment(path=path, name=name, is_active=False, ts_token=ts_token))

    # Deterministic order: rotated by filename timestamp only, then name.
    rotated.sort(key=lambda seg: (seg.ts_token or "", seg.name))

    # Duplicate timestamp tokens imply ambiguous ordering.
    seen_ts: set[str] = set()
    for seg in rotated:
        assert seg.ts_token is not None
        if seg.ts_token in seen_ts:
            errors.append(_err("SEGMENT_GAP", segment=seg.name, detail="duplicate_segment_timestamp"))
        seen_ts.add(seg.ts_token)

    ordered = [seg for seg in rotated] + [seg for seg in segments if seg.is_active]
    return ordered, errors, ignored_files


def _load_seals(seals_path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if not seals_path.exists():
        return {}, []
    if not seals_path.is_file():
        return {}, [_err("SEAL_HASH_MISMATCH", segment=seals_path.name, detail="seals_path_not_file")]

    errors: list[dict[str, Any]] = []
    by_segment: dict[str, dict[str, Any]] = {}
    with seals_path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(_err("SEAL_HASH_MISMATCH", segment=seals_path.name, line=line_no, detail=f"invalid_json:{exc}"))
                continue
            if not isinstance(row, dict):
                errors.append(_err("SEAL_HASH_MISMATCH", segment=seals_path.name, line=line_no, detail="non_object_json"))
                continue
            seg_name = row.get("segment_name")
            if not isinstance(seg_name, str) or not seg_name.strip():
                errors.append(_err("SEAL_HASH_MISMATCH", segment=seals_path.name, line=line_no, detail="missing_segment_name"))
                continue
            by_segment[seg_name] = row
    return by_segment, errors


def _verify_segment(path: Path, *, deep: bool) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    first_hash: str | None = None
    last_hash: str | None = None
    line_count = 0
    prev_hash: str | None = None

    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                return None, _err("HASH_CHAIN_BREAK", segment=path.name, line=line_no, detail="invalid_json")
            if not isinstance(entry, dict):
                return None, _err("HASH_CHAIN_BREAK", segment=path.name, line=line_no, detail="non_object_json")

            entry_hash = entry.get("hash")
            if not isinstance(entry_hash, str) or not entry_hash:
                return None, _err("HASH_CHAIN_BREAK", segment=path.name, line=line_no, detail="missing_hash")

            if line_count == 0:
                first_hash = entry_hash
            else:
                if entry.get("prev_hash") != prev_hash:
                    return None, _err("HASH_CHAIN_BREAK", segment=path.name, line=line_no, detail="prev_hash_mismatch")

            if deep:
                computed = _canonical_entry_hash(entry)
                if computed != entry_hash:
                    return None, _err("HASH_CHAIN_BREAK", segment=path.name, line=line_no, detail="hash_mismatch")

            prev_hash = entry_hash
            last_hash = entry_hash
            line_count += 1

    return {
        "first_hash": first_hash,
        "last_hash": last_hash,
        "line_count": line_count,
    }, None


def _verify_seal(segment: Segment, summary: dict[str, Any], seal: dict[str, Any] | None) -> dict[str, Any] | None:
    if seal is None:
        return _err("SEAL_MISSING", segment=segment.name)

    seal_first = seal.get("first_hash")
    seal_last = seal.get("last_hash")
    seal_count = seal.get("line_count")
    seal_hash = seal.get("seal_hash")

    if seal_count != summary["line_count"]:
        return _err("LINE_COUNT_MISMATCH", segment=segment.name)
    if seal_first != summary["first_hash"] or seal_last != summary["last_hash"]:
        return _err("HASH_CHAIN_BREAK", segment=segment.name, detail="seal_boundary_hash_mismatch")
    if not isinstance(seal_hash, str) or not seal_hash:
        return _err("SEAL_HASH_MISMATCH", segment=segment.name, detail="missing_seal_hash")

    calc = _sha256_text(
        f"{segment.name}{summary['first_hash'] or ''}{summary['last_hash'] or ''}{summary['line_count']}"
    )
    if calc != seal_hash:
        return _err("SEAL_HASH_MISMATCH", segment=segment.name)
    return None


def audit_segments(
    logs_dir: Path,
    *,
    deep: bool,
    enforce_seals: bool,
    strict_discovery: bool,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    segments, discover_errors, ignored_files = _discover_segments(logs_dir, strict_discovery=strict_discovery)
    errors.extend(discover_errors)

    seals_path = logs_dir / "rotation_seals.jsonl"
    seals, seal_load_errors = _load_seals(seals_path)
    errors.extend(seal_load_errors)

    sealed_segments = 0
    unsealed_segments = 0

    for seg in segments:
        summary, err = _verify_segment(seg.path, deep=deep)
        if err:
            errors.append(err)
            break
        assert summary is not None

        if seg.is_active:
            unsealed_segments += 1
            continue

        seal_err = _verify_seal(seg, summary, seals.get(seg.name))
        if seal_err is None:
            sealed_segments += 1
        else:
            unsealed_segments += 1
            if enforce_seals:
                errors.append(seal_err)
                break

    if enforce_seals and unsealed_segments > 1:
        errors.append(_err("SEAL_MISSING", segment="__aggregate__", detail="unsealed_segments_gt_1"))

    first_failure = errors[0]["type"] if errors else None
    return {
        "ok": len(errors) == 0,
        "mode": "deep" if deep else "fast",
        "logs_dir": str(logs_dir),
        "seals_path": str(seals_path),
        "seal_enforced": enforce_seals,
        "strict_discovery": strict_discovery,
        "segments_total": len(segments),
        "sealed_segments": sealed_segments,
        "unsealed_segments": unsealed_segments,
        "ignored_files": ignored_files,
        "first_failure": first_failure,
        "errors": errors[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit activity feed segment durability (fast/deep).")
    parser.add_argument("--runtime-root", type=Path, help="Runtime root (default from LUKA_RUNTIME_ROOT or ~/0luka_runtime)")
    parser.add_argument("--logs-dir", type=Path, help="Override logs directory directly")
    parser.add_argument("--deep", action="store_true", help="Recompute entry hashes and chain")
    parser.add_argument("--enforce-seals", action="store_true", help="Fail on missing/unsealed rotated segments")
    parser.add_argument(
        "--strict-discovery",
        action="store_true",
        help="Fail when archive has activity_feed*.jsonl entries that do not match canonical timestamped segment naming",
    )
    parser.add_argument("--json", action="store_true", help="Emit compact JSON")
    args = parser.parse_args()

    logs_dir = args.logs_dir if args.logs_dir else ((args.runtime_root / "logs") if args.runtime_root else _default_logs_dir())
    report = audit_segments(
        logs_dir,
        deep=args.deep,
        enforce_seals=args.enforce_seals,
        strict_discovery=args.strict_discovery,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
