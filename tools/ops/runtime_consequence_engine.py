#!/usr/bin/env python3
"""
tools/ops/runtime_consequence_engine.py — Sovereign Consequence Execution Engine
Implements the 3-Layer Safety Gate and Stateless Reconciliation.
"""
from __future__ import annotations
import json
import yaml
import sys
import os
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
POLICY_PATH = ROOT / "core/governance/runtime_consequence_policy.yaml"
QUERY_TOOL = ROOT / "tools/ops/activity_feed_query.py"
FEED_PATH = ROOT / "observability/logs/activity_feed.jsonl"

# --- 1. Governance Allowlist ---
ALLOWED_TARGETS = {"opal_api", "task_dispatcher", "com.0luka.kernel", "com.0luka.obs"}
ALLOWED_ACTIONS = {"throttle", "task_suppression", "restart_component", "emit_event", "suppress_new_tasks"}

def run_query(action: str, last_min: int = 1440, limit: int = 100) -> List[Dict[str, Any]]:
    """O(log n) index query via query tool."""
    cmd = [sys.executable, str(QUERY_TOOL), "--action", action, "--last-min", str(last_min), "--limit", str(limit), "--json"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        return data.get("results", [])
    except subprocess.CalledProcessError as e:
        print(f"Index Query Subprocess Failed (Code {e.returncode}):\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Index Query Parsing Failed: {e}", file=sys.stderr)
        return []

def get_now_utc() -> datetime:
    return datetime.now(timezone.utc)

def emit_event(action: str, data: Dict[str, Any]):
    """Immutable Ledger Append."""
    ts = get_now_utc().isoformat().replace("+00:00", "") + "Z"
    event = {
        "ts_utc": ts,
        "action": action,
        "emit_mode": "runtime_auto",
        "verifier_mode": "policy_execution"
    }
    event.update(data)
    try:
        with open(FEED_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        print(f"CRITICAL: Failed to append ledger: {e}", file=sys.stderr)
        sys.exit(1)

# --- 2. Stateless Reconciliation ---
def get_active_consequences() -> Dict[str, Dict[str, Any]]:
    """Reconstruct active state from the last 24 hours of ledger entries."""
    engaged = run_query("consequence_engaged", last_min=1440)
    released = run_query("consequence_expired", last_min=1440)
    reverted = run_query("consequence_reverted", last_min=1440)
    
    print(f"DEBUG: Found {len(engaged)} engaged, {len(released)} released, {len(reverted)} reverted")

    # Key by (type, target)
    active = {}
    
    # Process engagements
    for ev in sorted(engaged, key=lambda x: x["ts_utc"]):
        etype = ev.get("consequence_type")
        target = ev.get("target")
        if etype and target:
            active[(etype, target)] = ev
            print(f"DEBUG: Active Engagement: {etype} on {target} at {ev.get('ts_utc')}")

    # Remove if expired/reverted
    for ev in released + reverted:
        etype = ev.get("consequence_type")
        target = ev.get("target")
        key = (etype, target)
        if key in active:
            if ev["ts_utc"] > active[key]["ts_utc"]:
                print(f"DEBUG: Releasing {etype} on {target} due to {ev.get('action')}")
                del active[key]
                
    return active

def reconcile_expirations(active: Dict[tuple, Dict[str, Any]], confirmed: bool):
    """Check TTLs and emit expiration events."""
    now = get_now_utc()
    for (etype, target), ev in active.items():
        ttl = ev.get("details", {}).get("ttl_seconds", 0)
        if ttl <= 0: continue
        
        start_ts = datetime.fromisoformat(ev["ts_utc"].replace("Z", "+00:00"))
        if start_ts + timedelta(seconds=ttl) < now:
            print(f"Consequence Expired: {etype} on {target}")
            if confirmed:
                emit_event("consequence_expired", {
                    "consequence_type": etype,
                    "target": target,
                    "level": "INFO",
                    "message": f"TTL {ttl}s exceeded. Reverting."
                })

# --- 3. Safety Gates ---
def execute_rule(rule: Dict[str, Any], confirmed: bool, env_enabled: bool):
    """Evaluate and execute consequences with 3-layer gate."""
    rule_id = rule.get("id")
    match_cfg = rule.get("match", {})
    cond = rule.get("condition", {})
    
    action_match = match_cfg.get("action")
    last_min = cond.get("duration_minutes", 10)
    min_events = cond.get("min_events", 1)

    # 1. Trigger Check (Index)
    triggers = run_query(action_match, last_min=last_min)
    if "level" in match_cfg:
        triggers = [t for t in triggers if t.get("level") == match_cfg["level"]]
    
    if len(triggers) < min_events:
        return

    print(f"Policy Triggered: {rule_id}")
    
    layer1_dry = not confirmed
    layer2_env = env_enabled
    
    for cons in rule.get("consequences", []):
        ctype = cons.get("type")
        target = cons.get("target")
        ttl = cons.get("ttl_seconds", 0)
        
        if ctype not in ALLOWED_ACTIONS or target not in ALLOWED_TARGETS:
            print(f"REJECTED: Target/Action not allowed: {ctype} -> {target}", file=sys.stderr)
            continue
            
        print(f"Action: {ctype} on {target} (TTL: {ttl}s) | STATUS: {'ENGAGING' if (confirmed and env_enabled) else 'DRY_RUN'}")
        
        if confirmed and env_enabled:
            emit_event("consequence_engaged", {
                "consequence_type": ctype,
                "target": target,
                "level": "HIGH",
                "details": {"ttl_seconds": ttl, "rule_id": rule_id},
                "message": f"Sovereign automated remediation: {rule_id}"
            })
        else:
            if not env_enabled:
                print("GATE: CONSEQUENCE_ENABLED=1 not found in environment.")

def main():
    parser = argparse.ArgumentParser(description="0luka Sovereign Consequence Engine")
    parser.add_argument("--confirmed", action="store_true", help="Layer 3: Explicit confirmation")
    args = parser.parse_args()

    env_enabled = os.environ.get("CONSEQUENCE_ENABLED") == "1"
    
    if not POLICY_PATH.exists():
        print("Policy missing.")
        sys.exit(1)
        
    with open(POLICY_PATH, "r") as f:
        policy = yaml.safe_load(f)

    # 1. Reconcile Existing State (Expiration)
    active = get_active_consequences()
    reconcile_expirations(active, args.confirmed and env_enabled)

    # 2. Evaluate New Rules
    for rule in policy.get("rules", []):
        execute_rule(rule, args.confirmed, env_enabled)

    print(json.dumps({"status": "idle" if not (args.confirmed and env_enabled) else "active", "ts_utc": get_now_utc().isoformat()}))

if __name__ == "__main__":
    main()
