#!/usr/bin/env python3
"""
Dispatch Ledger v1 - append-only history of dispatched tasks.

Usage:
    python3 core/ledger.py
    python3 core/ledger.py --since 2026-02-08
    python3 core/ledger.py --status committed
    python3 core/ledger.py --json
    python3 core/ledger.py --rebuild
"""
from __future__ import annotations

import json
import os
import time
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from core.config import DISPATCH_LEDGER, DISPATCH_LOG, ROOT
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.config import DISPATCH_LEDGER, DISPATCH_LOG, ROOT

LEDGER_PATH = DISPATCH_LEDGER


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _empty_ledger() -> Dict[str, Any]:
    return {
        "schema_version": "dispatch_ledger_v1",
        "updated_at": _utc_now(),
        "entries": [],
        "summary": {
            "total": 0,
            "committed": 0,
            "rejected": 0,
            "error": 0,
            "skipped": 0,
            "first_dispatch": "",
            "last_dispatch": "",
        },
    }


def _load_ledger() -> Dict[str, Any]:
    if LEDGER_PATH.exists():
        try:
            data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return _empty_ledger()


def _save_ledger(ledger: Dict[str, Any]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER_PATH.parent / ".dispatch_ledger.tmp"
    tmp.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, LEDGER_PATH)


def _recompute_summary(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "total": len(entries),
        "committed": 0,
        "rejected": 0,
        "error": 0,
        "skipped": 0,
        "first_dispatch": "",
        "last_dispatch": "",
    }
    for entry in entries:
        status = str(entry.get("status", "error"))
        if status in ("committed", "rejected", "error", "skipped"):
            summary[status] += 1
        else:
            summary["error"] += 1
    timestamps = sorted([str(e.get("ts", "")) for e in entries if e.get("ts")])
    summary["first_dispatch"] = timestamps[0] if timestamps else ""
    summary["last_dispatch"] = timestamps[-1] if timestamps else ""
    return summary


def append_entry(
    task_id: str,
    status: str,
    *,
    author: str = "",
    intent: str = "",
    ts: str = "",
    audit_path: str = "",
) -> None:
    ledger = _load_ledger()
    entries = ledger.get("entries", [])
    if not isinstance(entries, list):
        entries = []

    existing_ids = {str(e.get("task_id")) for e in entries if isinstance(e, dict)}
    if task_id in existing_ids:
        return

    entry = {
        "task_id": task_id,
        "status": status,
        "author": author,
        "intent": intent,
        "ts": ts or _utc_now(),
        "audit_path": audit_path,
    }
    entries.append(entry)
    ledger["entries"] = entries
    ledger["summary"] = _recompute_summary(entries)
    ledger["updated_at"] = _utc_now()
    _save_ledger(ledger)


def rebuild_from_log() -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    seen_ids = set()

    if DISPATCH_LOG.exists():
        for line in DISPATCH_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("event") in ("watch_start", "watch_stop", "watch_cycle"):
                continue
            task_id = str(event.get("task_id", "")).strip()
            status = str(event.get("status", "")).strip()
            if not task_id or not status or task_id in seen_ids:
                continue
            seen_ids.add(task_id)
            entries.append(
                {
                    "task_id": task_id,
                    "status": status,
                    "author": str(event.get("author", "")),
                    "intent": str(event.get("intent", "")),
                    "ts": str(event.get("ts", "")),
                    "audit_path": str(event.get("audit_path", "")),
                }
            )

    ledger = {
        "schema_version": "dispatch_ledger_v1",
        "updated_at": _utc_now(),
        "entries": entries,
        "summary": _recompute_summary(entries),
    }
    _save_ledger(ledger)
    return ledger


def query(*, since: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    ledger = _load_ledger()
    entries = ledger.get("entries", [])
    if not isinstance(entries, list):
        return []
    filtered = entries
    if since:
        filtered = [e for e in filtered if str(e.get("ts", "")) >= since]
    if status:
        filtered = [e for e in filtered if str(e.get("status", "")) == status]
    return filtered


def _print_human(entries: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    print("0luka Dispatch Ledger")
    print("=" * 60)
    if not entries:
        print("(no entries)")
    else:
        for entry in entries:
            state = str(entry.get("status", "error"))
            icon = "ok" if state == "committed" else state
            print(f"  [{icon:>10s}] {entry.get('task_id', ''):<40s} {entry.get('ts', '')}")
    print()
    print(
        f"Total: {summary.get('total', 0)}  "
        f"Committed: {summary.get('committed', 0)}  "
        f"Rejected: {summary.get('rejected', 0)}  "
        f"Error: {summary.get('error', 0)}"
    )
    if summary.get("first_dispatch"):
        print(f"Range: {summary.get('first_dispatch', '')} .. {summary.get('last_dispatch', '')}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Dispatch Ledger v1")
    parser.add_argument("--since", type=str, help="Filter entries since date (YYYY-MM-DD)")
    parser.add_argument("--status", type=str, help="Filter by status")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild from dispatcher.jsonl")
    args = parser.parse_args()

    if args.rebuild:
        ledger = rebuild_from_log()
        if args.json:
            print(json.dumps(ledger, indent=2, ensure_ascii=False))
        else:
            _print_human(ledger.get("entries", []), ledger.get("summary", {}))
        return 0

    entries = query(since=args.since, status=args.status)
    ledger = _load_ledger()
    if args.json:
        print(json.dumps({"entries": entries, "summary": ledger.get("summary", {})}, indent=2, ensure_ascii=False))
    else:
        _print_human(entries, ledger.get("summary", {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
