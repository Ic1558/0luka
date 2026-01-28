#!/usr/bin/env python3
"""
Resilience Validation: Kill Service → Launchd Restart → Health Check
Proves system can recover from process termination.
"""
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(os.environ.get("ROOT", Path.cwd())).resolve()

# You must set these to match your service.
# From your logs: opal_api ran on 127.0.0.1:7001 (uvicorn)
HEALTH_URL = os.environ.get("HEALTH_URL", "http://127.0.0.1:7001/health")
PROCESS_MATCH = os.environ.get("PROCESS_MATCH", "opal_api|uvicorn|mcp_server|mcp")  # adjust
TIMEOUT_S = int(os.environ.get("RES_TIMEOUT_S", "45"))

def sh(cmd, check=True):
    return subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True).stdout.strip()

def curl_ok():
    # -f fail on non-2xx, -s silent
    try:
        sh(f"curl -fsS {HEALTH_URL} >/dev/null")
        return True
    except subprocess.CalledProcessError:
        return False

def kill_service():
    # Kill first matching PID
    out = sh(f"pgrep -f '{PROCESS_MATCH}' | head -n 1", check=False).strip()
    if not out:
        raise AssertionError(f"No PID found for PROCESS_MATCH={PROCESS_MATCH}")
    pid = out.splitlines()[0].strip()
    sh(f"kill -9 {pid}")
    return pid

def main():
    print(f"ROOT={ROOT}")
    print(f"HEALTH_URL={HEALTH_URL}")
    print(f"PROCESS_MATCH={PROCESS_MATCH}")

    if not curl_ok():
        raise AssertionError("Health check failed before kill (service not alive or wrong HEALTH_URL)")

    pid = kill_service()
    print(f"Killed PID={pid}")

    # Wait for auto-restart
    deadline = time.time() + TIMEOUT_S
    while time.time() < deadline:
        if curl_ok():
            print("OK: service recovered after kill")
            return 0
        time.sleep(1)

    raise AssertionError(f"Service did not recover within {TIMEOUT_S}s")

if __name__ == "__main__":
    raise SystemExit(main())
