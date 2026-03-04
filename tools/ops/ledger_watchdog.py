#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

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


def _utc_compact() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT")
    if raw is None or not raw.strip():
        raise RuntimeError("missing_env:LUKA_RUNTIME_ROOT")
    return Path(raw).expanduser().resolve()


def _canonical_feed_path() -> Path:
    return _runtime_root() / "logs" / "activity_feed.jsonl"


def _canonical_epoch_manifest_path() -> Path:
    return _runtime_root() / "logs" / "epoch_manifest.jsonl"


def _default_reports_dir(runtime_root: Path) -> Path:
    return runtime_root / "state" / "reports"


def _legacy_repo_reports_dir() -> Path:
    return ROOT / "g" / "reports"


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


def _read_compat_fail_reports(report_dirs: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for base in report_dirs:
        if not base.exists() or not base.is_dir():
            continue
        paths.extend(base.glob(f"{LEDGER_WATCHDOG_EPOCH_FAIL_PREFIX}*.md"))
        paths.extend(base.glob(f"{LEDGER_WATCHDOG_FAIL_PREFIX_LEGACY}*.md"))
    return sorted(paths, key=lambda p: (p.stat().st_mtime_ns, p.name))


def _write_fail_report(path: Path, report: dict[str, Any], report_dir: Path) -> Path:
    stamp = _utc_compact()
    report_dir.mkdir(parents=True, exist_ok=True)
    out = report_dir / f"{LEDGER_WATCHDOG_EPOCH_FAIL_PREFIX}{stamp}.md"
    errors = _summary_errors(report, limit=5)
    legacy_repo = _legacy_repo_reports_dir()
    previous_reports = _read_compat_fail_reports([report_dir, legacy_repo])
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


def _auto_heal_env(runtime_root: Path) -> list[str]:
    actions: list[str] = []
    log_dir = runtime_root / "logs"
    archive_dir = log_dir / "archive"
    state_dir = runtime_root / "state"
    reports_dir = state_dir / "reports"
    for d in (log_dir, archive_dir, state_dir, reports_dir):
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            actions.append(f"mkdir:{d}")
    return actions


def _remediation_hint(primary_failure: str | None) -> str:
    if primary_failure == "active_feed":
        return "investigate missing/corrupt activity_feed.jsonl or rotation seals"
    if primary_failure == "epoch_manifest":
        return "investigate epoch_manifest.jsonl continuity/hash mismatch"
    if primary_failure == "rotated_feeds":
        return "investigate archive feed chain/anchors in rotated files"
    return "investigate watchdog integrity incident"


def _emit_remediation_request(runtime_root: Path, payload: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    req_path = runtime_root / "state" / "remediation_requests.jsonl"
    # BEST-EFFORT: Only write if directory exists (do not create runtime root/state)
    if not req_path.parent.is_dir():
        return None, f"missing_dir:{req_path.parent}"
    try:
        with req_path.open("a", encoding="utf-8") as f:
            line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            f.write(line + "\n")
        return str(req_path), None
    except Exception as exc:
        return None, f"append_failed:{exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ledger runtime hash-chain watchdog.")
    parser.add_argument("--path", type=Path, help="Override feed path (default: runtime canonical feed)")
    parser.add_argument("--epoch-path", type=Path, help="Override epoch manifest path (default: runtime canonical path)")
    parser.add_argument("--check-epoch", action="store_true", help="Also verify epoch manifest chain and head completeness")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parser.add_argument("--no-emit", action="store_true", help="Do not emit integrity incident event on FAIL")
    parser.add_argument("--heal", action="store_true", help="Create required runtime log dirs only (no ledger mutation).")
    parser.add_argument("--emit-remediation", action="store_true", help="Append remediation request under $LUKA_RUNTIME_ROOT/state on FAIL.")
    parser.add_argument("--report-dir", type=Path, help="Override fail report directory (default: $LUKA_RUNTIME_ROOT/state/reports)")
    parser.add_argument("--no-report", action="store_true", help="Do not write fail report files.")
    args = parser.parse_args()

    healing_attempted = False
    healing_actions: list[str] = []
    remediation_emitted = False
    remediation_path: Optional[str] = None
    remediation_error: Optional[str] = None

    try:
        runtime_root = _runtime_root()
    except Exception as exc:
        missing_detail = str(exc)
        exit_code = 2
        report = {
            "ok": False,
            "exit_code": exit_code,
            "error": "runtime_root_missing",
            "detail": missing_detail,
            "report_path": None,
            "emitted": False,
            "checks": {
                "active_feed": {"ok": False, "path": None, "errors": [{"error": "runtime_root_missing"}]},
                "epoch_manifest": {"ok": False, "path": None, "errors": [{"error": "runtime_root_missing"}]},
                "rotated_feeds": {"ok": False, "files_total": 0, "files": []},
            },
            "primary_failure": "active_feed",
            "healing_attempted": False,
            "healing_actions": [],
            "remediation_emitted": False,
            "remediation_path": None,
            "remediation_error": None,
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(f"ledger_watchdog:fail error={report['error']} detail={report['detail']}", file=sys.stderr)
        return exit_code

    if args.heal:
        healing_attempted = True
        healing_actions = _auto_heal_env(runtime_root)

    canonical = _canonical_feed_path().resolve()
    target = (args.path.expanduser().resolve() if args.path else canonical)
    report_dir = (args.report_dir.expanduser().resolve() if args.report_dir else _default_reports_dir(runtime_root))
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
        if not args.no_report:
            report_path = _write_fail_report(target, combined_report, report_dir)
        if should_emit and report_path is not None:
            emitted = _emit_integrity_failed(target, combined_report, report_path)

        if args.emit_remediation:
            payload = {
                "ts_utc": _utc_compact(),
                "tool": "ledger_watchdog",
                "mode": "check_epoch",
                "primary_failure": primary_failure,
                "rc": 2,
                "runtime_root": str(runtime_root),
                "paths": {
                    "active_feed_path": str(target),
                    "epoch_path": str(epoch_target),
                    "rotated_glob": str(runtime_root / "logs" / "archive" / "activity_feed.*.jsonl"),
                },
                "heads": {
                    "active_feed_last_hash": feed_report.get("last_hash"),
                    "epoch_last_epoch_hash": epoch_report.get("last_epoch_hash") if isinstance(epoch_report, dict) else None,
                },
                "checks_summary": {
                    "active_feed": {
                        "ok": bool(feed_report.get("ok")),
                        "lines_total": int(feed_report.get("lines_total", 0) or 0),
                    },
                    "epoch_manifest": {
                        "ok": bool(epoch_report.get("ok")) if isinstance(epoch_report, dict) else False,
                        "lines_total": int(epoch_report.get("lines_total", 0) or 0) if isinstance(epoch_report, dict) else 0,
                    },
                    "rotated_feeds": {
                        "ok": bool(rotated_report.get("ok")) if isinstance(rotated_report, dict) else False,
                        "files_total": int(rotated_report.get("files_total", 0) or 0) if isinstance(rotated_report, dict) else 0,
                    },
                },
                "hint": _remediation_hint(primary_failure),
            }
            remediation_path, remediation_error = _emit_remediation_request(runtime_root, payload)
            remediation_emitted = remediation_path is not None
            if remediation_emitted:
                remediation_error = None
    exit_code = 0 if ok else 2

    if args.json:
        out = {
            "ok": ok,
            "exit_code": exit_code,
            "error": None,
            "path": str(target),
            "epoch_path": str(epoch_target) if args.check_epoch else None,
            "canonical_path": str(canonical),
            "canonical_epoch_path": str(canonical_epoch_path),
            "report_path": str(report_path) if report_path else None,
            "emitted": emitted,
            "healing_attempted": healing_attempted,
            "healing_actions": healing_actions,
            "remediation_emitted": remediation_emitted,
            "remediation_path": remediation_path,
            "remediation_error": remediation_error,
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

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
