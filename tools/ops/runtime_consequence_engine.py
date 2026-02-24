#!/usr/bin/env python3
import json
import yaml
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
POLICY_PATH = ROOT / "core/governance/runtime_consequence_policy.yaml"
QUERY_TOOL = ROOT / "tools/ops/activity_feed_query.py"
FEED_PATH = ROOT / "observability/logs/activity_feed.jsonl"

def run_query(action: str, last_min: int) -> Dict[str, Any]:
    cmd = [sys.executable, str(QUERY_TOOL), "--action", action, "--last-min", str(last_min), "--json"]
    print(f"DEBUG: Running query cmd: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        print(f"DEBUG: Query matched={data.get('matched_count')} count={data.get('results_count')}")
        return data
    except Exception as e:
        print(f"Query failed: {e}", file=sys.stderr)
        return {"ok": False, "results": [], "matched_count": 0}

def emit_consequence(action: str, target: str, consequence_type: str, details: Dict[str, Any]):
    ts = datetime.utcnow().isoformat() + "Z"
    event = {
        "ts_utc": ts,
        "action": action,
        "emit_mode": "runtime_auto",
        "level": "HIGH",
        "consequence_type": consequence_type,
        "target": target,
        "details": details,
        "verifier_mode": "policy_execution"
    }
    try:
        with open(FEED_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")
        print(f"Emitted consequence event: {action} on {target}")
    except Exception as e:
        print(f"Failed to emit event: {e}", file=sys.stderr)

def execute_consequences(consequences: List[Dict[str, Any]]):
    for cons in consequences:
        c_type = cons.get("type")
        target = cons.get("target", "system")
        params = cons.get("params", {})
        
        if c_type == "emit_event":
            # Direct event emission
            emit_consequence(cons.get("action", "consequence_executed"), target, c_type, params)
        elif c_type in ["throttle", "task_suppression", "restart_component"]:
            # In a real system, these would call actual APIs/System signals.
            # Here, we record the intended action as a proof event.
            emit_consequence("consequence_engaged", target, c_type, {
                "params": params,
                "status": "ENGAGED",
                "message": f"Simulated {c_type} on {target}"
            })
        else:
            print(f"Unknown consequence type: {c_type}", file=sys.stderr)

def main():
    if not POLICY_PATH.exists():
        print(f"Policy file missing: {POLICY_PATH}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(POLICY_PATH, "r") as f:
            policy = yaml.safe_load(f)
    except Exception as e:
        print(f"POLICY_MALFORMED: {e}", file=sys.stderr)
        sys.exit(1)

    rules = policy.get("rules", [])
    executed_count = 0

    for rule in rules:
        match = rule.get("match", {})
        cond = rule.get("condition", {})
        
        action = match.get("action")
        last_min = cond.get("duration_minutes", 10)
        min_events = cond.get("min_events", 1)
        
        if not action: continue
        
        # 1. Query Index
        res = run_query(action, last_min)
        if not res.get("ok"): continue
        
        # 2. Evaluate
        matches = res.get("results", [])
        # Check level match if specified
        if "level" in match:
            matches = [m for m in matches if m.get("level") == match["level"]]
            
        if len(matches) >= min_events:
            print(f"Rule triggered: {rule.get('id')} ({len(matches)} matches)")
            # 3. Execute
            execute_consequences(rule.get("consequences", []))
            executed_count += 1

    print(json.dumps({
        "status": "complete",
        "rules_evaluated": len(rules),
        "rules_triggered": executed_count,
        "ts_utc": datetime.utcnow().isoformat() + "Z"
    }))

if __name__ == "__main__":
    main()
