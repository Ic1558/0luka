#!/usr/bin/env python3
"""
Remediator - The Brain
Analyzes snapshots for anomalies and generates signed remediation commands.
"""
import sys
import json
import time
import hashlib
import uuid
import re
from pathlib import Path
from datetime import datetime, timedelta

# Paths
INBOX = Path("~/02luka/interface/inbox").expanduser()
SECRET_FILE = Path("~/.0luka/.mary_key").expanduser()
REMEDIATION_DIR = Path("~/0luka/artifacts/remediation").expanduser()
COOLDOWN_STATE = REMEDIATION_DIR / "cooldown_state.json"

# Detection Rules
PORT_RULES = [
    {"port": 7001, "action": "RESTART_AGENT", "name": "Uvicorn/Agent"}
]

LOG_PATTERNS = [
    {"pattern": r"FATAL:", "action": "GET_PROCESSES", "name": "Fatal Error"}
]

def load_secret():
    """Load shared secret for signing"""
    with open(SECRET_FILE, 'r') as f:
        return f.read().strip().split('=')[1]

def sign_command(cmd, secret):
    """Generate HMAC-SHA256 signature"""
    raw = json.dumps(cmd, sort_keys=True)
    return hashlib.sha256((raw + secret).encode()).hexdigest()

def check_cooldown(action, cooldown_seconds=300):
    """Check if action is in cooldown period"""
    if not COOLDOWN_STATE.exists():
        return False
    
    with open(COOLDOWN_STATE, 'r') as f:
        state = json.load(f)
    
    last_trigger = state.get(action)
    if last_trigger:
        elapsed = time.time() - last_trigger
        if elapsed < cooldown_seconds:
            print(f"[SKIP] {action} is in cooldown ({int(cooldown_seconds - elapsed)}s remaining)")
            return True
    
    return False

def update_cooldown(action):
    """Update cooldown state"""
    state = {}
    if COOLDOWN_STATE.exists():
        with open(COOLDOWN_STATE, 'r') as f:
            state = json.load(f)
    
    state[action] = time.time()
    with open(COOLDOWN_STATE, 'w') as f:
        json.dump(state, f, indent=2)

def trigger_remediation(action, params={}, reason=""):
    """Generate and send signed command"""
    if check_cooldown(action):
        return False
    
    secret = load_secret()
    cmd_id = str(uuid.uuid4())
    cmd = {
        "id": cmd_id,
        "timestamp": time.time(),
        "action": action,
        "params": params
    }
    cmd['signature'] = sign_command(cmd, secret)
    
    # Write to inbox
    INBOX.mkdir(parents=True, exist_ok=True)
    with open(INBOX / "command.json", 'w') as f:
        json.dump(cmd, f, indent=2)
    
    # Log evidence
    evidence_file = REMEDIATION_DIR / f"{datetime.now().strftime('%y%m%d_%H%M%S')}_{action}.json"
    with open(evidence_file, 'w') as f:
        json.dump({
            "command_id": cmd_id,
            "action": action,
            "params": params,
            "reason": reason,
            "timestamp": time.time()
        }, f, indent=2)
    
    update_cooldown(action)
    print(f"[REMEDIATION] Issued {action} (ID: {cmd_id}) - {reason}")
    print(f"[EVIDENCE] Saved to {evidence_file}")
    return True

def detect_port_failures(snapshot_content):
    """Detect missing expected ports"""
    findings = []
    
    for rule in PORT_RULES:
        port = rule['port']
        # Check if port appears in LISTEN state
        if f":{port} (LISTEN)" not in snapshot_content and f"*:{port}" not in snapshot_content:
            findings.append({
                "type": "port_failure",
                "port": port,
                "action": rule['action'],
                "reason": f"Port {port} ({rule['name']}) not in LISTEN state"
            })
    
    return findings

def detect_log_anomalies(snapshot_content):
    """Detect problematic patterns in logs"""
    findings = []
    
    for rule in LOG_PATTERNS:
        pattern = re.compile(rule['pattern'])
        if pattern.search(snapshot_content):
            findings.append({
                "type": "log_anomaly",
                "pattern": rule['pattern'],
                "action": rule['action'],
                "reason": f"Detected pattern: {rule['name']}"
            })
    
    return findings

def analyze_snapshot(snapshot_path):
    """Main analysis function"""
    print(f"[REMEDIATOR] Analyzing snapshot: {snapshot_path}")
    
    with open(snapshot_path, 'r') as f:
        content = f.read()
    
    # Run detections
    port_failures = detect_port_failures(content)
    log_anomalies = detect_log_anomalies(content)
    
    all_findings = port_failures + log_anomalies
    
    if not all_findings:
        print("[REMEDIATOR] No anomalies detected")
        return
    
    print(f"[REMEDIATOR] Found {len(all_findings)} anomalies")
    
    # Trigger remediation for each finding
    for finding in all_findings:
        params = {}
        if finding['type'] == 'port_failure':
            params['port'] = finding['port']
        
        trigger_remediation(
            action=finding['action'],
            params=params,
            reason=finding['reason']
        )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: remediator.py <snapshot_file>")
        sys.exit(1)
    
    snapshot_file = Path(sys.argv[1])
    if not snapshot_file.exists():
        print(f"Error: Snapshot file not found: {snapshot_file}")
        sys.exit(1)
    
    REMEDIATION_DIR.mkdir(parents=True, exist_ok=True)
    analyze_snapshot(snapshot_file)
