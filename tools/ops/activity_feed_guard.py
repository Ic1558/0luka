#!/usr/bin/env python3
import json
import sys
import time
from datetime import datetime
from pathlib import Path

DEFAULT_FEED = "observability/logs/activity_feed.jsonl"
HEARTBEAT_TIMEOUT = 600  # 10 minutes
BURST_LIMIT = 100        # Events per 10 seconds (anomaly)

def run_guard(feed_path: Path):
    if not feed_path.exists():
        print(f"error: feed_missing at {feed_path}", file=sys.stderr)
        return 1

    try:
        lines = feed_path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        print(f"error: read_failed: {exc}", file=sys.stderr)
        return 1

    if not lines:
        return 0

    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except:
            continue
    
    if not events:
        return 0

    now_utc = datetime.utcnow()
    last_event = events[-1]
    last_ts_str = last_event.get("ts_utc")
    
    # 1. Detect Silent Gaps (Heartbeat Loss)
    if last_ts_str:
        try:
            # Handle both ISO formats
            last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
            gap = (now_utc.timestamp() - last_ts.timestamp())
            if gap > HEARTBEAT_TIMEOUT:
                emit_anomaly(feed_path, "heartbeat_lost", f"No events for {int(gap)}s")
        except Exception:
            pass

    # 2. Detect Backwards Movement / Sequence Anomalies
    last_ms = 0
    anomalies = []
    for i, ev in enumerate(events):
        curr_ms = ev.get("ts_epoch_ms")
        if not curr_ms:
            # fallback to ts_utc if ms missing
            ts_str = ev.get("ts_utc")
            if ts_str:
                try:
                    curr_ms = int(datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp() * 1000)
                except: continue
        
        if curr_ms and last_ms and curr_ms < last_ms:
            anomalies.append(f"time_regression at line {i+1}")
        
        if curr_ms:
            last_ms = curr_ms

    if anomalies:
        emit_anomaly(feed_path, "sequence_regression", "; ".join(anomalies[:5]))

    # 3. Correlation: Unresolved System Pressure (RAM CRITICAL + Maintenance NOOP)
    check_escalation(feed_path, events)

    return 0

def check_escalation(feed_path, events):
    # Scan last 50 events for context
    recent = events[-50:]
    has_ram_crit = any(e.get("action") == "ram_pressure_persistent" and e.get("level") == "CRITICAL" for e in recent)
    has_maint_noop = any(e.get("action") == "activity_feed_maintenance" and e.get("result") == "noop" for e in recent)
    
    # Simple check: if we have both in the recent window, we are stuck
    if has_ram_crit and has_maint_noop:
        # Check if we already complained recently to avoid spam
        if not any(e.get("action") == "system_pressure_unresolved" for e in recent[-10:]):
            ts = datetime.utcnow().isoformat() + "Z"
            escalation = {
                "ts_utc": ts,
                "action": "system_pressure_unresolved",
                "emit_mode": "runtime_auto",
                "level": "HIGH",
                "message": "RAM critical persists despite maintenance noop"
            }
            with open(feed_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(escalation) + "\n")
            print("escalation_emitted: system_pressure_unresolved", file=sys.stderr)

def emit_anomaly(feed_path, type, message):
    ts = datetime.utcnow().isoformat() + "Z"
    event = {
        "ts_utc": ts,
        "action": "feed_anomaly",
        "emit_mode": "runtime_auto",
        "level": "CRITICAL",
        "anomaly_type": type,
        "message": message
    }
    with open(feed_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    print(f"anomaly_detected: {type}: {message}", file=sys.stderr)

if __name__ == "__main__":
    feed = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_FEED)
    sys.exit(run_guard(feed))
