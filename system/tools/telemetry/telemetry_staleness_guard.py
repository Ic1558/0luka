#!/usr/bin/env python3
import json
import os
import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone

# 0luka Root
ROOT = Path(os.environ.get("ROOT", str(Path.home() / "0luka"))).resolve()
CONFIG_PATH = ROOT / "system/tools/telemetry/staleness_guard_targets.json"
INCIDENT_LOG = ROOT / "observability/incidents/tk_incidents.jsonl"
STATE_DIR = ROOT / "observability/artifacts/staleness"

# Fields to exclude from fingerprint
VOLATILE_FIELDS = {"ts", "updated_at", "host", "module", "meta", "pid"}

def get_fingerprint(data):
    """Normalize JSON and return a stable hash string."""
    filtered = {k: v for k, v in data.items() if k not in VOLATILE_FIELDS}
    # Stable sort and stringify
    stable_json = json.dumps(filtered, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()

def emit_incident(module, path, same_count, current_hash, last_ts):
    now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    incident = {
        "ts": now_ts,
        "kind": "telemetry_frozen",
        "module": module,
        "path": str(path),
        "same_count": same_count,
        "hash": current_hash,
        "last_ts_seen": last_ts,
        "now_ts": now_ts
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with INCIDENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(incident) + "\n")
    print(f"INCIDENT: {module} telemetry frozen for {same_count} checks.")

def main():
    if not CONFIG_PATH.exists():
        print(f"DEGRADED: Config missing: {CONFIG_PATH}")
        return 2

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"DEGRADED: Invalid config: {e}")
        return 2

    exit_code = 0
    now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for target in config.get("targets", []):
        module = target["module"]
        rel_path = target["path"]
        abs_path = ROOT / rel_path
        threshold = target.get("threshold", 3)
        is_critical = target.get("critical", False)

        state_file = STATE_DIR / f"{module}.state.json"
        
        if not abs_path.exists():
            print(f"DEGRADED: {module} telemetry not found at {rel_path}")
            if exit_code == 0: exit_code = 2
            continue

        try:
            data = json.loads(abs_path.read_text(encoding="utf-8"))
            current_hash = get_fingerprint(data)
            current_ts = data.get("ts", "unknown")
        except Exception as e:
            print(f"DEGRADED: Error reading {module}: {e}")
            if exit_code == 0: exit_code = 2
            continue

        # Load State
        state = {"last_hash": None, "same_count": 0, "last_ts_seen": None}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
            except:
                pass

        # Logic
        is_idle = False
        status_val = str(data.get("status", "")).lower()
        if module == "bridge_consumer":
            if "idle" in status_val or "no_new_files" in str(data.get("note", "")):
                is_idle = True
        elif module == "executor_lisa":
            if "idle" in status_val or data.get("processed", 0) == 0:
                is_idle = True
        
        if current_hash == state["last_hash"]:
            if is_idle:
                state["same_count"] = 0
                print(f"IDLE: {module} unchanged hash but idle (reset count)")
            else:
                state["same_count"] += 1
                print(f"MATCH: {module} hash unchanged (count={state['same_count']})")
        else:
            state["same_count"] = 0
            print(f"RESET: {module} hash changed.")

        state["last_hash"] = current_hash
        state["last_ts_seen"] = current_ts
        state["last_run_ts"] = now_ts

        # Save State
        state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

        # Threshold Check
        if state["same_count"] >= threshold:
            emit_incident(module, rel_path, state["same_count"], current_hash, current_ts)
            exit_code = 64

    return exit_code

if __name__ == "__main__":
    import sys
    sys.exit(main())
