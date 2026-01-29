#!/usr/bin/env python3
"""
Session Recorder - Watches bridge_watch telemetry and records session events.

This is a minimal implementation to stabilize the launchd module.
Full implementation TBD based on session recording requirements.
"""
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("LUKA_ROOT", str(Path.home() / "0luka"))).resolve()
TELEMETRY_PATH = Path(os.environ.get("SESSION_TELEMETRY_PATH", "observability/telemetry/bridge_watch.latest.json"))
OUT_DIR = Path(os.environ.get("SESSION_OUT_DIR", "g/session"))
POLL_SEC = int(os.environ.get("SESSION_POLL_SEC", "2"))
COOLDOWN_SEC = int(os.environ.get("SESSION_COOLDOWN_SEC", "10"))

running = True


def signal_handler(signum, frame):
    global running
    running = False
    print(f"Received signal {signum}, shutting down...")


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main():
    global running
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    out_dir = ROOT / OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    
    tele_path = ROOT / TELEMETRY_PATH if not TELEMETRY_PATH.is_absolute() else TELEMETRY_PATH
    
    print(f"Session recorder started at {now_utc()}")
    print(f"  Telemetry: {tele_path}")
    print(f"  Output: {out_dir}")
    print(f"  Poll: {POLL_SEC}s, Cooldown: {COOLDOWN_SEC}s")
    
    last_check = None
    
    while running:
        try:
            if tele_path.exists():
                mtime = tele_path.stat().st_mtime
                if last_check is None or mtime > last_check:
                    last_check = mtime
                    # Log that we saw an update (minimal implementation)
                    # Full implementation would record session events here
                    pass
            
            time.sleep(POLL_SEC)
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(COOLDOWN_SEC)
    
    print(f"Session recorder stopped at {now_utc()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
