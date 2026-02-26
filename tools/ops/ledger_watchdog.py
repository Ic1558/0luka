#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

from tools.ops.audit_feed_chain import _audit
from tools.ops.audit_epoch_manifest import _audit_epoch_manifest

LEDGER_WATCHDOG_EPOCH_FAIL_PREFIX = "ledger_watchdog_epoch_fail_"
LEDGER_WATCHDOG_FAIL_PREFIX_LEGACY = "ledger_watchdog_fail_"  # backward-compat read-only


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
        return _audit(path)
    if not path.exists():
        return _audit(path)
    with path.open("rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            return _audit(path)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _run_epoch_audit_with_shared_lock(path: Path) -> dict[str, Any]:
    if fcntl is None:
        return _audit_epoch_manifest(path)
    if not path.exists():
        return _audit_epoch_manifest(path)
    with path.open("rb") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            return _audit_epoch_manifest(path)
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
