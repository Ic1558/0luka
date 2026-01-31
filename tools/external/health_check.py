#!/usr/bin/env python3
# tools/external/health_check.py
# D3: Remote Health Endpoint (System Vitals)

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(os.environ.get("ROOT", str(Path(__file__).parent.parent.parent))).resolve()
STATE_DIR = ROOT / "state"
OBS_DIR = ROOT / "observability"

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def main():
    # 1. Check Pause
    paused_file = STATE_DIR / "librarian" / "PAUSE"
    paused = paused_file.exists()
    
    # 2. Check Librarian Vitals
    lib_ts = None
    lib_exit = None
    current_system = STATE_DIR / "current_system.json"
    if current_system.exists():
        try:
            sys_data = json.loads(current_system.read_text())
            lib_ts = sys_data.get("librarian", {}).get("last_run_ts_utc")
        except: pass
        
    # Check last exit code from launchd log logic? 
    # Or just rely on fail_count file if exists
    fail_count = 0
    fail_file = STATE_DIR / "librarian" / "fail_count.txt"
    if fail_file.exists():
        try:
             fail_count = int(fail_file.read_text().strip())
        except: pass

    # 3. Check Bridge Vitals
    bridge_telemetry = OBS_DIR / "telemetry" / "bridge_consumer.latest.json"
    bridge_ts = None
    bridge_status = "unknown"
    inbox_count = 0 # Need brief info or real count
    if bridge_telemetry.exists():
        try:
            b_data = json.loads(bridge_telemetry.read_text())
            bridge_ts = b_data.get("ts")
            bridge_status = b_data.get("status")
        except: pass

    # 4. Briefing Vitals
    dash_progress = OBS_DIR / "dashboard" / "progress" / "latest.json"
    briefing_ts = None
    counts = {}
    if dash_progress.exists():
        try:
            d_data = json.loads(dash_progress.read_text())
            briefing_ts = d_data.get("generated_at")
            counts = d_data.get("counts", {})
        except: pass

    # 5. Incidents
    incidents_file = OBS_DIR / "incidents" / "tk_incidents.jsonl"
    incident_count_24h = 0
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    if incidents_file.exists():
        try:
            lines = incidents_file.read_text(encoding="utf-8").strip().splitlines()
            for line in lines:
                try:
                    entry = json.loads(line)
                    ts_str = entry.get("ts", "")
                    # handle iso format
                    # 2026-01-31T10:25:13+00:00 or Z
                    if ts_str.endswith("Z"):
                        ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    else:
                        ts_dt = datetime.fromisoformat(ts_str)
                    
                    if ts_dt >= cutoff:
                        incident_count_24h += 1
                except: pass
        except: pass

    # Output Structure
    vitals = {
        "ts_utc": now_utc_iso(),
        "healthy": not paused and fail_count < 3 and incident_count_24h < 10, # Arbitrary health logic
        "paused": paused,
        "incidents_24h": incident_count_24h,
        "components": {
            "librarian": {
                "last_run": lib_ts,
                "fail_count": fail_count
            },
            "bridge": {
                "last_run": bridge_ts,
                "status": bridge_status
            },
            "briefing": {
                "last_generated": briefing_ts
            }
        },
        "counts": counts # Inbox, Pending, etc.
    }
    
    print(json.dumps(vitals, indent=2))

if __name__ == "__main__":
    main()
