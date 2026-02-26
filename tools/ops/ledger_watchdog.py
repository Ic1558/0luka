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
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from tools.ops.audit_feed_chain import _audit as _audit_feed_chain_ext
except Exception:  # pragma: no cover - fallback kept for transition safety
    _audit_feed_chain_ext = None  # type: ignore[assignment]

try:
    from tools.ops.audit_epoch_manifest import _audit_epoch_manifest as _audit_epoch_manifest_ext
except Exception:  # pragma: no cover - fallback kept for transition safety
    _audit_epoch_manifest_ext = None  # type: ignore[assignment]

LEDGER_WATCHDOG_EPOCH_FAIL_PREFIX = "ledger_watchdog_epoch_fail_"
LEDGER_WATCHDOG_FAIL_PREFIX_LEGACY = "ledger_watchdog_fail_"  # backward-compat read-only
GENESIS_PREV_HASH = "GENESIS"
ANCHOR_ACTION = "ledger_anchor"
GENESIS_PREV_EPOCH_HASH = "0000000000000000"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT")
    if raw is None or not raw.strip():
        raise RuntimeError("missing_env:LUKA_RUNTIME_ROOT")
    return Path(raw).expanduser().resolve()


def _canonical_feed_path() -> Path:
    return _runtime_root() / "logs" / "activity_feed.jsonl"


def _canonical_epoch_manifest_path() -> Path:
    return _runtime_root() / "logs" / "epoch_manifest.jsonl"


def _reports_dir() -> Path:
    path = ROOT / "g" / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _summary_errors(report: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    errs = report.get("errors")
    if not isinstance(errs, list):
        return []
    out: list[dict[str, Any]] = []
    for item in errs[:limit]:
        if isinstance(item, dict):
            out.append(item)
        else:
            out.append({"error": str(item)})
    return out


def _fallback_compute_feed_hash(entry: dict[str, Any]) -> str:
    payload = dict(entry)
    payload.pop("hash", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _fallback_audit_feed_chain(path: Path) -> dict[str, Any]:
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
                computed = _fallback_compute_feed_hash(entry)
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
            computed = _fallback_compute_feed_hash(entry)
            if computed != entry_hash:
                errors.append({"line": line_no, "error": "hash_mismatch", "computed": computed, "stored": entry_hash})
                continue
            if entry.get("prev_hash") != last_hash:
                errors.append(
                    {
                        "line": line_no,
                        "error": "prev_hash_mismatch",
                        "expected": last_hash,
                        "observed": entry.get("prev_hash"),
                    }
                )
                continue
            hashed_lines += 1
            last_hash = entry_hash

    return {
        "ok": len(errors) == 0,
        "path": str(path),
        "lines_total": lines_total,
        "legacy_lines": legacy_lines,
        "hashed_lines": hashed_lines,
        "anchor_seen": anchor_seen,
        "first_anchor_line": first_anchor_line,
        "last_hash": last_hash,
        "rotation_registry_path": str(path.parent / "rotation_registry.jsonl"),
        "rotation_entries_checked": 0,
        "errors": errors[:5],
    }


def _fallback_compute_epoch_hash(epoch_id: int, prev_epoch_hash: str, log_heads: dict[str, Any]) -> str:
    canonical = str(epoch_id) + prev_epoch_hash + json.dumps(log_heads, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fallback_validate_head_shape(head: Any) -> bool:
    if not isinstance(head, dict):
        return False
    if (
        isinstance(head.get("path"), str)
        and isinstance(head.get("exists"), bool)
        and isinstance(head.get("size_bytes"), int)
        and isinstance(head.get("tail_sha256"), str)
    ):
        return True
    if (
        isinstance(head.get("last_event_hash"), str)
        and isinstance(head.get("line_count"), int)
    ):
        return True
    return False


def _fallback_audit_epoch_manifest(path: Path) -> dict[str, Any]:
    required_logs = ["dispatcher"]
    if not path.exists():
        return {
            "ok": False,
            "path": str(path),
            "lines_total": 0,
            "epoch_lines": 0,
            "required_logs": required_logs,
            "head_completeness_ok": False,
            "first_epoch_line": None,
            "last_epoch_hash": None,
            "errors": [{"line": 0, "error": f"missing_file:{path}"}],
        }
    if not path.is_file():
        return {
            "ok": False,
            "path": str(path),
            "lines_total": 0,
            "epoch_lines": 0,
            "required_logs": required_logs,
            "head_completeness_ok": False,
            "first_epoch_line": None,
            "last_epoch_hash": None,
            "errors": [{"line": 0, "error": f"not_a_file:{path}"}],
        }

    errors: list[dict[str, Any]] = []
    lines_total = 0
    epoch_lines = 0
    first_epoch_line: int | None = None
    last_epoch_hash: str | None = None
    head_completeness_ok = True

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
            epoch_hash = entry.get("epoch_hash")
            log_heads = entry.get("log_heads")
            if not isinstance(epoch_id, int) or epoch_id < 1:
                errors.append({"line": line_no, "error": "invalid_epoch_id"})
                continue
            if not isinstance(prev_epoch_hash, str) or not prev_epoch_hash:
                errors.append({"line": line_no, "error": "invalid_prev_epoch_hash"})
                continue
            if not isinstance(epoch_hash, str) or not epoch_hash:
                errors.append({"line": line_no, "error": "invalid_epoch_hash"})
                continue
            if not isinstance(log_heads, dict):
                errors.append({"line": line_no, "error": "invalid_log_heads"})
                continue

            if first_epoch_line is None:
                first_epoch_line = line_no
                if prev_epoch_hash != GENESIS_PREV_EPOCH_HASH:
                    errors.append(
                        {
                            "line": line_no,
                            "error": "genesis_prev_epoch_hash_mismatch",
                            "expected": GENESIS_PREV_EPOCH_HASH,
                            "observed": prev_epoch_hash,
                        }
                    )
            elif prev_epoch_hash != last_epoch_hash:
                errors.append(
                    {
                        "line": line_no,
                        "error": "prev_epoch_hash_mismatch",
                        "expected": last_epoch_hash,
                        "observed": prev_epoch_hash,
                    }
                )

            missing = [key for key in required_logs if key not in log_heads]
            if missing:
                head_completeness_ok = False
                errors.append({"line": line_no, "error": "missing_registered_head", "missing": missing})
            for key in required_logs:
                if key not in log_heads:
                    continue
                if not _fallback_validate_head_shape(log_heads[key]):
                    head_completeness_ok = False
                    errors.append({"line": line_no, "error": "invalid_log_head_shape", "log": key})
            if "activity_feed" in log_heads:
                head_completeness_ok = False
                errors.append({"line": line_no, "error": "forbidden_log_head", "log": "activity_feed"})

            computed = _fallback_compute_epoch_hash(epoch_id, prev_epoch_hash, log_heads)
            if computed != epoch_hash:
                errors.append({"line": line_no, "error": "epoch_hash_mismatch", "computed": computed, "stored": epoch_hash})
                continue
            epoch_lines += 1
            last_epoch_hash = epoch_hash

    return {
        "ok": len(errors) == 0,
        "path": str(path),
        "lines_total": lines_total,
        "epoch_lines": epoch_lines,
        "required_logs": required_logs,
        "head_completeness_ok": head_completeness_ok,
        "first_epoch_line": first_epoch_line,
        "last_epoch_hash": last_epoch_hash,
        "errors": errors[:5],
    }


def _audit_feed(path: Path) -> dict[str, Any]:
    if _audit_feed_chain_ext is not None:
        return _audit_feed_chain_ext(path)
    return _fallback_audit_feed_chain(path)


def _audit_epoch(path: Path) -> dict[str, Any]:
    if _audit_epoch_manifest_ext is not None:
        return _audit_epoch_manifest_ext(path)
    return _fallback_audit_epoch_manifest(path)


def _read_compat_fail_reports() -> list[Path]:
    base = _reports_dir()
    paths = [
        *base.glob(f"{LEDGER_WATCHDOG_EPOCH_FAIL_PREFIX}*.md"),
        *base.glob(f"{LEDGER_WATCHDOG_FAIL_PREFIX_LEGACY}*.md"),
    ]
    return sorted(paths, key=lambda p: (p.stat().st_mtime_ns, p.name))


def _write_fail_report(path: Path, report: dict[str, Any]) -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = _reports_dir() / f"{LEDGER_WATCHDOG_EPOCH_FAIL_PREFIX}{stamp}.md"
    errors = _summary_errors(report, limit=5)
    previous_reports = _read_compat_fail_reports()
    previous_latest = str(previous_reports[-1]) if previous_reports else None
    lines = [
        "# Ledger Watchdog Epoch Failure",
        "",
        f"- ts_utc: {_utc_now()}",
        f"- feed_path: {path}",
        f"- previous_fail_report: {previous_latest}",
        "",
        "## Audit Report",
        "",
        "```json",
        json.dumps(report, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Error Summary",
        "",
        "```json",
        json.dumps(errors, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _emit_integrity_failed(path: Path, report: dict[str, Any], report_path: Path) -> bool:
    failed_checks: list[str] = []
    feed_report = report.get("active_feed")
    epoch_report = report.get("epoch_manifest")
    rotated_report = report.get("rotated_feeds")
    if isinstance(feed_report, dict) and not bool(feed_report.get("ok")):
        failed_checks.append("active_feed")
    if isinstance(epoch_report, dict) and not bool(epoch_report.get("ok")):
        failed_checks.append("epoch_manifest")
    if isinstance(rotated_report, dict) and not bool(rotated_report.get("ok")):
        failed_checks.append("rotated_feeds")
    from core.activity_feed_guard import guarded_append_activity_feed

    payload = {
        "ts_utc": _utc_now(),
        "ts_epoch_ms": int(time.time_ns() // 1_000_000),
        "phase_id": "LEDGER_WATCHDOG",
        "action": "ledger_integrity_failed",
        "emit_mode": "runtime_auto",
        "verifier_mode": "operational_proof",
        "tool": "ledger_watchdog",
        "status_badge": "NOT_PROVEN",
        "detail": {
            "path": str(path),
            "report_path": str(report_path),
            "failed_checks": failed_checks,
            "summary": {
                "feed_errors": _summary_errors(feed_report if isinstance(feed_report, dict) else {}, limit=3),
                "epoch_errors": _summary_errors(epoch_report if isinstance(epoch_report, dict) else {}, limit=3),
                "rotated_errors": _summary_errors(rotated_report if isinstance(rotated_report, dict) else {}, limit=3),
            },
        },
    }
    return guarded_append_activity_feed(_canonical_feed_path(), payload)


def _run_audit_with_shared_lock(path: Path) -> dict[str, Any]:
    if fcntl is None:
        return _audit_feed(path)
    if not path.exists():
        return _audit_feed(path)
    with path.open("rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            return _audit_feed(path)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _run_epoch_audit_with_shared_lock(path: Path) -> dict[str, Any]:
    if fcntl is None:
        return _audit_epoch(path)
    if not path.exists():
        return _audit_epoch(path)
    with path.open("rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            return _audit_epoch(path)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _list_rotated_feed_files(runtime_root: Path) -> list[Path]:
    archive_dir = runtime_root / "logs" / "archive"
    if not archive_dir.exists() or not archive_dir.is_dir():
        return []
    files = [p for p in archive_dir.glob("activity_feed.*.jsonl") if p.is_file()]
    return sorted(files, key=lambda p: p.name)


def _run_rotated_feeds_audit(runtime_root: Path) -> dict[str, Any]:
    files = _list_rotated_feed_files(runtime_root)
    rows: list[dict[str, Any]] = []
    ok = True
    for path in files:
        report = _run_audit_with_shared_lock(path)
        rows.append(report)
        if not bool(report.get("ok")):
            ok = False
    return {
        "ok": ok,
        "files_total": len(files),
        "files": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ledger runtime hash-chain watchdog.")
    parser.add_argument("--path", type=Path, help="Override feed path (default: runtime canonical feed)")
    parser.add_argument("--epoch-path", type=Path, help="Override epoch manifest path (default: runtime canonical path)")
    parser.add_argument("--check-epoch", action="store_true", help="Also verify epoch manifest chain and head completeness")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parser.add_argument("--no-emit", action="store_true", help="Do not emit integrity incident event on FAIL")
    args = parser.parse_args()

    try:
        runtime_root = _runtime_root()
    except Exception as exc:
        report = {
            "ok": False,
            "error": "runtime_root_missing",
            "detail": str(exc),
            "checks": {
                "active_feed": None,
                "epoch_manifest": None,
                "rotated_feeds": None,
            },
            "primary_failure": "active_feed",
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(f"ledger_watchdog:fail error={report['error']} detail={report['detail']}", file=sys.stderr)
        return 2

    canonical = _canonical_feed_path().resolve()
    target = (args.path.expanduser().resolve() if args.path else canonical)
    canonical_epoch_path = _canonical_epoch_manifest_path().resolve()
    epoch_target = args.epoch_path.expanduser().resolve() if args.epoch_path else canonical_epoch_path

    feed_report = _run_audit_with_shared_lock(target)
    epoch_report: dict[str, Any] | None = None
    rotated_report: dict[str, Any] | None = None
    if args.check_epoch:
        epoch_report = _run_epoch_audit_with_shared_lock(epoch_target)
        rotated_report = _run_rotated_feeds_audit(runtime_root)

    ok = bool(feed_report.get("ok"))
    if epoch_report is not None:
        ok = ok and bool(epoch_report.get("ok"))
    if rotated_report is not None:
        ok = ok and bool(rotated_report.get("ok"))
    primary_failure: str | None = None
    if not bool(feed_report.get("ok")):
        primary_failure = "active_feed"
    elif epoch_report is not None and not bool(epoch_report.get("ok")):
        primary_failure = "epoch_manifest"
    elif rotated_report is not None and not bool(rotated_report.get("ok")):
        primary_failure = "rotated_feeds"

    combined_report = {
        "ok": ok,
        "active_feed": feed_report,
        "epoch_manifest": epoch_report,
        "rotated_feeds": rotated_report,
        "primary_failure": primary_failure,
    }

    should_emit = (
        (not args.no_emit)
        and (target == canonical)
        and (not args.check_epoch or epoch_target == canonical_epoch_path)
    )
    report_path: Path | None = None
    emitted = False

    if not ok:
        report_path = _write_fail_report(target, combined_report)
        if should_emit:
            emitted = _emit_integrity_failed(target, combined_report, report_path)

    if args.json:
        out = {
            "ok": ok,
            "path": str(target),
            "epoch_path": str(epoch_target) if args.check_epoch else None,
            "canonical_path": str(canonical),
            "canonical_epoch_path": str(canonical_epoch_path),
            "report_path": str(report_path) if report_path else None,
            "emitted": emitted,
            "checks": {
                "active_feed": feed_report,
                "epoch_manifest": epoch_report,
                "rotated_feeds": rotated_report,
            },
            "primary_failure": primary_failure,
        }
        print(json.dumps(out, ensure_ascii=False))
    else:
        if ok:
            if args.check_epoch:
                print(f"ledger_watchdog:ok path={target} epoch_path={epoch_target}")
            else:
                print(f"ledger_watchdog:ok path={target}")
        else:
            print(f"ledger_watchdog:fail path={target} report={report_path} emitted={emitted}", file=sys.stderr)

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
