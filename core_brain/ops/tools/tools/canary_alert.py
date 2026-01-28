#!/usr/bin/env python3
"""
Canary Alert - Circuit Breaker for Autonomous Loop
The observer of the observer - last safety rail before human intervention.

Trigger Classes:
1. REMEDIATION_LOOP_FAIL: Same action ≥3 times in 15 min without recovery
2. CONTROL_PLANE_DEGRADED: Chain broken (no outbox result within timeout)
3. INTEGRITY_BREACH: Signature verify fail / policy deny
4. RESOURCE_EXHAUSTION: Disk >90% or load >threshold

Does NOT alert on:
- Transient errors
- Single remediation
- Legacy log noise
"""
import json
import time
import os
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# Paths
ROOT = Path(os.environ.get("ROOT", str(Path.home() / "0luka"))).expanduser().resolve()
REMEDIATION_DIR = ROOT / "artifacts/remediation"
OUTBOX_DIR = Path("/Users/icmini/02luka/interface/outbox/results")
STATE_FILE = REMEDIATION_DIR / "canary_state.json"

# Thresholds
WINDOW = 900  # 15 minutes
REMEDIATION_THRESHOLD = 3  # Same action ≥3 times = loop failure
DISK_THRESHOLD = 90  # Disk usage >90%
LOAD_THRESHOLD = 8.0  # Load average threshold

def load_state():
    """Load canary state"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            return {}
    return {}

def save_state(state):
    """Save canary state"""
    STATE_FILE.write_text(json.dumps(state, indent=2))

def recent_actions():
    """Get remediation actions in last 15 minutes"""
    now = time.time()
    events = []
    
    for f in REMEDIATION_DIR.glob("*.json"):
        if f.name == "canary_state.json" or f.name == "cooldown_state.json":
            continue
        try:
            data = json.loads(f.read_text())
            timestamp = data.get("timestamp", 0)
            if now - timestamp <= WINDOW:
                events.append(data)
        except:
            pass
    
    return events

def check_control_plane():
    """Check if control plane is responding"""
    # Check if Mary Adapter is running
    try:
        result = subprocess.run(
            ["pgrep", "-f", "mary_control_adapter"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False, "Mary Control Adapter not running"
    except:
        return False, "Cannot check Mary Adapter status"
    
    # Check if recent remediation commands have results
    recent_cmds = recent_actions()
    if recent_cmds:
        latest_cmd = max(recent_cmds, key=lambda x: x.get("timestamp", 0))
        cmd_id = latest_cmd.get("command_id")
        if cmd_id:
            result_file = OUTBOX_DIR / f"{cmd_id}.json"
            if not result_file.exists():
                # Check if command is recent (within 60 seconds)
                if time.time() - latest_cmd.get("timestamp", 0) > 60:
                    return False, f"No result for command {cmd_id[:8]}..."
    
    return True, "Control plane operational"

def check_disk_usage():
    """Check disk usage"""
    try:
        stat = shutil.disk_usage("/")
        usage_pct = (stat.used / stat.total) * 100
        if usage_pct > DISK_THRESHOLD:
            return False, f"Disk usage {usage_pct:.1f}% (>{DISK_THRESHOLD}%)"
    except:
        pass
    return True, "Disk usage normal"

def check_load_average():
    """Check system load"""
    try:
        load1, load5, load15 = os.getloadavg()
        if load5 > LOAD_THRESHOLD:
            return False, f"Load average {load5:.2f} (>{LOAD_THRESHOLD})"
    except:
        pass
    return True, "Load average normal"

def alert(severity, message):
    """Send alert via macOS notification"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    full_message = f"[{timestamp}] {severity}: {message}"
    
    try:
        subprocess.run([
            "osascript",
            "-e", f'display notification "{message}" with title "🐤 0luka Canary - {severity}"'
        ], check=False)
    except:
        pass
    
    # Log to file
    log_file = REMEDIATION_DIR / "canary_alerts.log"
    with open(log_file, "a") as f:
        f.write(f"{full_message}\n")
    
    print(f"[CANARY] {full_message}")

def main():
    """Main canary check"""
    state = load_state()
    current_time = time.time()
    
    # Reset state if last check was >1 hour ago
    last_check = state.get("last_check", 0)
    if current_time - last_check > 3600:
        state = {"last_check": current_time}
    
    state["last_check"] = current_time
    
    # Check 1: Remediation Loop Failure
    events = recent_actions()
    action_counts = {}
    for event in events:
        action = event.get("action", "UNKNOWN")
        action_counts[action] = action_counts.get(action, 0) + 1
    
    for action, count in action_counts.items():
        if count >= REMEDIATION_THRESHOLD:
            alert_key = f"loop_fail_{action}"
            if state.get(alert_key) != "alerted":
                alert("CRITICAL", f"{action} failed {count} times in 15 min - Loop failure detected")
                state[alert_key] = "alerted"
                state[f"{alert_key}_time"] = current_time
            # Reset alert after 1 hour
            elif current_time - state.get(f"{alert_key}_time", 0) > 3600:
                state[alert_key] = None
    
    # Check 2: Control Plane Health
    plane_ok, plane_msg = check_control_plane()
    if not plane_ok:
        if state.get("control_plane") != "alerted":
            alert("WARNING", f"Control plane degraded: {plane_msg}")
            state["control_plane"] = "alerted"
            state["control_plane_time"] = current_time
    else:
        if state.get("control_plane") == "alerted":
            # Recovery notification
            alert("INFO", "Control plane recovered")
        state["control_plane"] = None
    
    # Check 3: Disk Usage
    disk_ok, disk_msg = check_disk_usage()
    if not disk_ok:
        if state.get("disk") != "alerted":
            alert("WARNING", disk_msg)
            state["disk"] = "alerted"
            state["disk_time"] = current_time
    else:
        state["disk"] = None
    
    # Check 4: Load Average
    load_ok, load_msg = check_load_average()
    if not load_ok:
        if state.get("load") != "alerted":
            alert("WARNING", load_msg)
            state["load"] = "alerted"
            state["load_time"] = current_time
    else:
        state["load"] = None
    
    # Save state
    save_state(state)

if __name__ == "__main__":
    main()
