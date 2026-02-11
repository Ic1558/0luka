#!/usr/bin/env python3
"""
Watchdog monitor - checks dispatcher health, stuck tasks, and tmp file cleanup.

Usage:
    python3 tools/ops/watchdog.py              # full check
    python3 tools/ops/watchdog.py --heartbeat  # heartbeat only
    python3 tools/ops/watchdog.py --cleanup    # tmp cleanup only
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(os.environ.get("ROOT") or Path(__file__).resolve().parents[2])
HEARTBEAT_PATH = ROOT / "observability" / "artifacts" / "dispatcher_heartbeat.json"
WATCHDOG_LOG = ROOT / "observability" / "incidents" / "watchdog.jsonl"
INBOX_DIR = ROOT / "interface" / "inbox"

# Thresholds
STALE_HEARTBEAT_SEC = 300  # 5 minutes
STUCK_TASK_SEC = 600  # 10 minutes
TMP_MAX_AGE_SEC = 300  # 5 minutes


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _log_incident(incident: Dict[str, Any]) -> None:
    """Append incident to watchdog log."""
    WATCHDOG_LOG.parent.mkdir(parents=True, exist_ok=True)
    incident.setdefault("ts", _utc_now())
    with WATCHDOG_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(incident, ensure_ascii=False) + "\n")


def check_heartbeat() -> Dict[str, Any]:
    """Check dispatcher heartbeat freshness."""
    if not HEARTBEAT_PATH.exists():
        return {"stale": True, "status": "missing", "age_sec": -1}

    try:
        hb = json.loads(HEARTBEAT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"stale": True, "status": "corrupt", "age_sec": -1}

    ts_str = str(hb.get("ts", "")).strip()
    if not ts_str:
        return {"stale": True, "status": "no_timestamp", "age_sec": -1}

    try:
        # Fix 5: Use datetime with explicit UTC timezone for correct age calculation
        hb_dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age_sec = time.time() - hb_dt.timestamp()
    except (ValueError, OSError):
        return {"stale": True, "status": "bad_timestamp", "age_sec": -1}

    is_stale = age_sec > STALE_HEARTBEAT_SEC
    return {
        "stale": is_stale,
        "status": str(hb.get("status", "unknown")),
        "age_sec": round(age_sec, 1),
        "pid": hb.get("pid"),
    }


def check_stuck_tasks() -> List[Dict[str, Any]]:
    """Find inbox tasks older than STUCK_TASK_SEC."""
    stuck = []
    if not INBOX_DIR.exists():
        return stuck

    now = time.time()
    for f in INBOX_DIR.iterdir():
        if not f.is_file():
            continue
        try:
            age = now - f.stat().st_mtime
        except OSError:
            continue
        if age > STUCK_TASK_SEC:
            stuck.append({
                "file": f.name,
                "age_sec": round(age, 1),
            })
    return stuck


def clean_tmp_files() -> int:
    """Remove stale .tmp files from artifacts directory."""
    artifacts_dir = ROOT / "observability" / "artifacts"
    if not artifacts_dir.exists():
        return 0

    cleaned = 0
    now = time.time()
    for tmp_file in artifacts_dir.rglob("*.tmp"):
        try:
            age = now - tmp_file.stat().st_mtime
            if age > TMP_MAX_AGE_SEC:
                tmp_file.unlink()
                cleaned += 1
                _log_incident({
                    "type": "tmp_cleaned",
                    "file": str(tmp_file.relative_to(ROOT)),
                    "age_sec": round(age, 1),
                })
        except OSError:
            continue
    return cleaned


def run_checks() -> Dict[str, Any]:
    """Run all watchdog checks."""
    hb = check_heartbeat()
    stuck = check_stuck_tasks()
    cleaned = clean_tmp_files()

    if hb["stale"]:
        _log_incident({"type": "stale_heartbeat", **hb})
    for s in stuck:
        _log_incident({"type": "stuck_task", **s})

    return {
        "ts": _utc_now(),
        "heartbeat": hb,
        "stuck_tasks": stuck,
        "tmp_cleaned": cleaned,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Watchdog Monitor")
    parser.add_argument("--heartbeat", action="store_true", help="Heartbeat check only")
    parser.add_argument("--cleanup", action="store_true", help="Tmp cleanup only")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.heartbeat:
        result = check_heartbeat()
    elif args.cleanup:
        result = {"tmp_cleaned": clean_tmp_files()}
    else:
        result = run_checks()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
