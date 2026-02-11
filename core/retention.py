#!/usr/bin/env python3
"""
Kernel retention module for V.2 pipeline artifacts.

Usage:
    python3 core/retention.py
    python3 core/retention.py --dry-run
    python3 core/retention.py --json
"""
from __future__ import annotations

import json
import os
import time
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from core.config import ROOT as CONFIG_ROOT
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.config import ROOT as CONFIG_ROOT

ROOT = Path(os.environ.get("ROOT") or CONFIG_ROOT)
ACTIVITY_PATH = ROOT / "observability" / "activity" / "activity.jsonl"

POLICY: Dict[str, Dict[str, Any]] = {
    "dispatcher_log": {
        "path": "observability/logs/dispatcher.jsonl",
        "type": "log_rotate",
        "max_size_kb": 1024,
        "keep_rotated": 3,
    },
    "router_audit": {
        "path": "observability/artifacts/router_audit",
        "type": "dir_age",
        "max_age_days": 30,
        "keep_min": 50,
    },
    "completed_tasks": {
        "path": "interface/completed",
        "type": "dir_age",
        "max_age_days": 14,
        "keep_min": 20,
    },
    "rejected_tasks": {
        "path": "interface/rejected",
        "type": "dir_age",
        "max_age_days": 14,
        "keep_min": 20,
    },
}

_PROTECTED_REL = {
    "observability/artifacts/dispatch_latest.json",
    "observability/artifacts/dispatch_ledger.json",
    "observability/artifacts/dispatcher_heartbeat.json",
}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _resolve_rel(path_str: str) -> Path:
    rel = Path(path_str)
    return ROOT / rel


def _is_protected(path: Path) -> bool:
    try:
        rel = str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("\\", "/")
    except Exception:
        return False
    return rel in _PROTECTED_REL


def _append_activity_event(event: Dict[str, Any]) -> None:
    """Append activity event atomically by temp + replace."""
    ACTIVITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if ACTIVITY_PATH.exists():
        try:
            existing = ACTIVITY_PATH.read_text(encoding="utf-8")
        except Exception:
            existing = ""
    line = json.dumps(event, ensure_ascii=False) + "\n"
    tmp = ACTIVITY_PATH.parent / ".activity.tmp"
    tmp.write_text(existing + line, encoding="utf-8")
    os.replace(tmp, ACTIVITY_PATH)


def _emit_activity(
    *,
    event_type: str,
    severity: str,
    summary: str,
    meta_path: str,
    bytes_value: int | None = None,
    keep_days: int | None = None,
    dry_run: bool = False,
) -> None:
    event: Dict[str, Any] = {
        "ts_utc": _utc_now(),
        "actor": "core.retention",
        "type": event_type,
        "severity": severity,
        "summary": summary,
        "meta": {
            "path": meta_path,
            "bytes": bytes_value if bytes_value is not None else 0,
            "keep_days": keep_days if keep_days is not None else 0,
            "dry_run": dry_run,
        },
    }
    _append_activity_event(event)


def rotate_log(policy_entry: Dict[str, Any], *, dry_run: bool = False) -> Dict[str, Any]:
    log_path = _resolve_rel(str(policy_entry.get("path", "")))
    max_size_kb = int(policy_entry.get("max_size_kb", 1024))
    keep_rotated = max(1, int(policy_entry.get("keep_rotated", 3)))

    if not log_path.exists() or not log_path.is_file():
        return {"rotated": False, "size_before_kb": 0}

    size_kb = int((log_path.stat().st_size + 1023) / 1024)
    should_rotate = size_kb > max_size_kb
    if not should_rotate:
        return {"rotated": False, "size_before_kb": size_kb}
    if dry_run:
        return {"rotated": True, "size_before_kb": size_kb, "would_rotate": True}

    oldest = log_path.with_name(f"{log_path.name}.{keep_rotated}")
    if oldest.exists():
        oldest.unlink()
    for idx in range(keep_rotated - 1, 0, -1):
        src = log_path.with_name(f"{log_path.name}.{idx}")
        dst = log_path.with_name(f"{log_path.name}.{idx + 1}")
        if src.exists():
            os.replace(src, dst)

    os.replace(log_path, log_path.with_name(f"{log_path.name}.1"))
    tmp = log_path.with_name(f".{log_path.name}.tmp")
    tmp.write_text("", encoding="utf-8")
    os.replace(tmp, log_path)
    return {"rotated": True, "size_before_kb": size_kb}


def age_directory(policy_entry: Dict[str, Any], *, dry_run: bool = False) -> Dict[str, Any]:
    dir_path = _resolve_rel(str(policy_entry.get("path", "")))
    max_age_days = int(policy_entry.get("max_age_days", 30))
    keep_min = max(0, int(policy_entry.get("keep_min", 0)))

    if not dir_path.exists() or not dir_path.is_dir():
        return {"deleted": 0, "remaining": 0}

    files = sorted(
        [p for p in dir_path.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    now = time.time()
    cutoff = now - (max_age_days * 86400)

    candidates = []
    protected_skipped = 0
    for idx, file_path in enumerate(files):
        if idx < keep_min:
            continue
        if _is_protected(file_path):
            protected_skipped += 1
            continue
        if file_path.stat().st_mtime < cutoff:
            candidates.append(file_path)

    would_delete = len(candidates)
    if dry_run:
        return {
            "deleted": 0,
            "remaining": len(files),
            "would_delete": would_delete,
            "protected_skipped": protected_skipped,
        }

    deleted = 0
    for file_path in candidates:
        try:
            file_path.unlink()
            deleted += 1
        except Exception:
            pass
    remaining = sum(1 for p in dir_path.iterdir() if p.is_file())
    return {"deleted": deleted, "remaining": remaining, "protected_skipped": protected_skipped}


def run_retention(*, dry_run: bool = False, policy: Dict[str, Dict[str, Any]] | None = None) -> Dict[str, Any]:
    active_policy = policy or POLICY
    results: Dict[str, Any] = {"schema_version": "retention_v1", "ts": _utc_now(), "dry_run": dry_run, "policies": {}}

    for name, entry in active_policy.items():
        entry_type = str(entry.get("type", ""))
        rel_path = str(entry.get("path", ""))
        try:
            if entry_type == "log_rotate":
                result = rotate_log(entry, dry_run=dry_run)
                results["policies"][name] = result
                if result.get("rotated"):
                    _emit_activity(
                        event_type="retention.rotate",
                        severity="info",
                        summary=f"{name} rotated",
                        meta_path=rel_path,
                        bytes_value=int(result.get("size_before_kb", 0) * 1024),
                        keep_days=None,
                        dry_run=dry_run,
                    )
            elif entry_type == "dir_age":
                result = age_directory(entry, dry_run=dry_run)
                results["policies"][name] = result
                keep_days = int(entry.get("max_age_days", 0))
                deleted = int(result.get("deleted", 0))
                would_delete = int(result.get("would_delete", 0))
                protected_skipped = int(result.get("protected_skipped", 0))
                if deleted > 0 or (dry_run and would_delete > 0):
                    count = would_delete if dry_run else deleted
                    _emit_activity(
                        event_type="retention.delete",
                        severity="warning",
                        summary=f"{name} removed {count} old files",
                        meta_path=rel_path,
                        bytes_value=0,
                        keep_days=keep_days,
                        dry_run=dry_run,
                    )
                if protected_skipped > 0:
                    _emit_activity(
                        event_type="retention.protected_skip",
                        severity="info",
                        summary=f"{name} skipped {protected_skipped} protected files",
                        meta_path=rel_path,
                        bytes_value=0,
                        keep_days=keep_days,
                        dry_run=dry_run,
                    )
            else:
                results["policies"][name] = {"error": f"unsupported_type:{entry_type}"}
                _emit_activity(
                    event_type="retention.error",
                    severity="error",
                    summary=f"{name} unsupported policy type",
                    meta_path=rel_path,
                    bytes_value=0,
                    keep_days=0,
                    dry_run=dry_run,
                )
        except Exception as exc:
            results["policies"][name] = {"error": f"{type(exc).__name__}:{exc}"}
            _emit_activity(
                event_type="retention.error",
                severity="error",
                summary=f"{name} retention failed",
                meta_path=rel_path,
                bytes_value=0,
                keep_days=int(entry.get("max_age_days", 0)) if entry_type == "dir_age" else 0,
                dry_run=dry_run,
            )

    return results


def _print_human(summary: Dict[str, Any]) -> None:
    print("0luka Kernel Retention")
    print("=" * 40)
    print(f"dry_run: {summary.get('dry_run')}")
    for name, result in (summary.get("policies") or {}).items():
        print(f"- {name}: {result}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Kernel retention module")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; do not delete or rotate")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    summary = run_retention(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        _print_human(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
