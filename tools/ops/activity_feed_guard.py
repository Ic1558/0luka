#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
import os
from datetime import datetime
from pathlib import Path
import argparse

DEFAULT_FEED = "observability/logs/activity_feed.jsonl"
HEARTBEAT_TIMEOUT = 600  # 10 minutes

def run_guard(feed_path: Path, once: bool = False, emit: bool = True) -> Dict[str, Any]:
    report = {
        "ok": True,
        "ts_utc": datetime.utcnow().isoformat() + "Z",
        "checks": {
            "heartbeat": {"ok": True},
            "sequence": {"ok": True},
            "escalation": {"found": False}
        },
        "anomalies": [],
        "emitted": []
    }

    if not feed_path.exists():
        report["ok"] = False
        report["error"] = "feed_missing"
        return report

    try:
        lines = feed_path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        report["ok"] = False
        report["error"] = f"read_failed: {exc}"
        return report

    events = []
    for line_no, line in enumerate(lines, start=1):
        line = line.strip()
        if not line: continue
        try:
            events.append((line_no, json.loads(line)))
        except:
            continue
    
    if not events:
        return report

    now_utc = datetime.utcnow()
    _, last_event = events[-1]
    last_ts_str = last_event.get("ts_utc")
    
    # 1. Heartbeat check
    if last_ts_str:
        try:
            last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
            gap = now_utc.timestamp() - last_ts.timestamp()
            if gap > HEARTBEAT_TIMEOUT:
                report["checks"]["heartbeat"] = {"ok": False, "gap_sec": int(gap)}
                msg = f"No events for {int(gap)}s"
                report["anomalies"].append({"type": "heartbeat_lost", "msg": msg})
                if emit:
                    emit_event(feed_path, "feed_anomaly", "CRITICAL", {"anomaly_type": "heartbeat_lost", "message": msg}, report)
        except: pass

    # 2. Sequence check
    last_ms = 0
    seq_errors = []
    for line_no, ev in events:
        curr_ms = ev.get("ts_epoch_ms")
        if not curr_ms:
            ts_str = ev.get("ts_utc")
            if ts_str:
                try:
                    curr_ms = int(datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp() * 1000)
                except: continue
        
        if curr_ms and last_ms and curr_ms < last_ms:
            seq_errors.append(f"line {line_no}")
        if curr_ms:
            last_ms = curr_ms

    if seq_errors:
        report["checks"]["sequence"] = {"ok": False, "errors": seq_errors}
        msg = f"Time regression at: {', '.join(seq_errors[:5])}"
        report["anomalies"].append({"type": "sequence_regression", "msg": msg})
        if emit:
            emit_event(feed_path, "feed_anomaly", "CRITICAL", {"anomaly_type": "sequence_regression", "message": msg}, report)

    # 3. Escalation check
    recent = [ev for _, ev in events[-50:]]
    has_ram_crit = any(e.get("action") == "ram_pressure_persistent" and e.get("level") == "CRITICAL" for e in recent)
    has_maint_noop = any(e.get("action") == "activity_feed_maintenance" and e.get("result") == "noop" for e in recent)
    
    if has_ram_crit and has_maint_noop:
        report["checks"]["escalation"]["found"] = True
        if not any(e.get("action") == "system_pressure_unresolved" for e in recent[-10:]):
            if emit:
                msg = "RAM critical persists despite maintenance noop"
                emit_event(feed_path, "system_pressure_unresolved", "HIGH", {"message": msg}, report)

    report["ok"] = len(report["anomalies"]) == 0
    return report

def emit_event(feed_path, action, level, data, report):
    ts = datetime.utcnow().isoformat() + "Z"
    event = {
        "ts_utc": ts,
        "action": action,
        "emit_mode": "runtime_auto",
        "level": level
    }
    event.update(data)
    try:
        with open(feed_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        report["emitted"].append(event)
    except:
        pass

def main():
    parser = argparse.ArgumentParser(description="0luka Activity Feed Guard")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parser.add_argument("--path", help="Path to activity feed")
    parser.add_argument("--no-emit", action="store_false", dest="emit", help="Don't append to feed")
    args = parser.parse_args()

    feed = Path(args.path) if args.path else Path(DEFAULT_FEED)
    report = run_guard(feed, once=args.once, emit=args.emit)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if not report["ok"]:
            for a in report["anomalies"]:
                print(f"ANOMALY: {a['type']}: {a['msg']}", file=sys.stderr)
        if report["emitted"]:
            for e in report["emitted"]:
                print(f"EMITTED: {e['action']} ({e['level']})", file=sys.stderr)
        print(f"Guard Status: {'OK' if report['ok'] else 'ANOMALY'} events_checked={report.get('ts_utc')}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
