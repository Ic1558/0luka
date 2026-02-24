#!/usr/bin/env python3
"""
tools/ops/sovereign_loop.py — Canonical Sovereign Loop Control Plane
"""
import json
import yaml
import sys
import os
import subprocess
import argparse
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
POLICY_PATH = ROOT / "core/governance/runtime_consequence_policy.yaml"
LOOP_POLICY_PATH = ROOT / "core/governance/sovereign_loop_policy.yaml"
QUERY_TOOL = ROOT / "tools/ops/activity_feed_query.py"
INDEX_DIR = ROOT / "observability/logs/index"
FEED_PATH = ROOT / "observability/logs/activity_feed.jsonl"
AUDIT_DIR = ROOT / "observability/artifacts/sovereign_runs"

ALLOWED_TARGETS = {"opal_api", "task_dispatcher", "com.0luka.kernel", "com.0luka.obs"}
ALLOWED_ACTIONS = {"throttle", "task_suppression", "restart_component", "emit_event", "suppress_new_tasks"}

def get_now_utc() -> datetime:
    return datetime.now(timezone.utc)

def get_file_sha256(path: Path) -> str:
    if not path.exists(): return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]

class SovereignControl:
    def __init__(self, confirmed: bool, replay_mode: bool = False, 
                 policy_path: Path = POLICY_PATH, 
                 loop_policy_path: Path = LOOP_POLICY_PATH,
                 query_tool: Path = QUERY_TOOL):
        self.confirmed = confirmed
        self.replay_mode = replay_mode
        self.run_id = uuid.uuid4().hex[:8]
        self.env_enabled = os.environ.get("CONSEQUENCE_ENABLED") == "1"
        self.decisions = []
        self.triggers_found = []
        
        # Paths
        self.policy_path = policy_path
        self.loop_policy_path = loop_policy_path
        self.query_tool = query_tool
        
        # Metadata
        self.policy_sha = get_file_sha256(self.policy_path)
        self.loop_policy_sha = get_file_sha256(self.loop_policy_path)
        self.engine_sha = get_file_sha256(Path(__file__))
        
        # Load policies
        with open(self.policy_path, "r") as f: self.consequence_policy = yaml.safe_load(f)
        with open(self.loop_policy_path, "r") as f: self.loop_policy = yaml.safe_load(f)

    def run_query(self, action: str, last_min: int = 1440, limit: int = 100) -> List[Dict[str, Any]]:
        cmd = [sys.executable, str(self.query_tool), "--action", action, "--last-min", str(last_min), "--limit", str(limit), "--json"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
            return [r for r in data.get("results", []) if "error" not in r]
        except Exception:
            return []

    def emit_event(self, action: str, data: Dict[str, Any]):
        if self.replay_mode: return
        ts = get_now_utc().isoformat().replace("+00:00", "") + "Z"
        event = {
            "ts_utc": ts,
            "action": action,
            "emit_mode": "runtime_auto",
            "verifier_mode": "control_plane"
        }
        event.update(data)
        with open(FEED_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")

    def check_rate_limits(self, ctype: str) -> bool:
        """Enforce global and per-consequence limits."""
        # 1. Global hourly limit
        all_actions = self.run_query("consequence_engaged", last_min=60)
        max_hourly = self.loop_policy.get("global_limits", {}).get("max_actions_per_hour", 20)
        if len(all_actions) >= max_hourly:
            self.emit_event("sovereign_rate_limited", {"reason": "global_hourly_cap_exceeded", "limit": max_hourly})
            return False

        # 2. Per-consequence cooldown
        cooldown = self.loop_policy.get("consequence_rules", {}).get(ctype, {}).get("min_interval_seconds", 0)
        if cooldown > 0:
            past_engaged = [a for a in all_actions if a.get("consequence_type") == ctype]
            if past_engaged:
                last_ts_str = sorted(past_engaged, key=lambda x: x["ts_utc"])[-1]["ts_utc"]
                last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
                if get_now_utc() - last_ts < timedelta(seconds=cooldown):
                    return False
        
        return True

    def reconcile(self):
        """Standard stateless reconciliation logic."""
        engaged = self.run_query("consequence_engaged", last_min=1440)
        released = self.run_query("consequence_expired", last_min=1440)
        reverted = self.run_query("consequence_reverted", last_min=1440)
        
        active = {}
        for ev in sorted(engaged, key=lambda x: x.get("ts_utc", "")):
            active[(ev.get("consequence_type"), ev.get("target"))] = ev
            
        for ev in released + reverted:
            key = (ev.get("consequence_type"), ev.get("target"))
            if key in active and ev["ts_utc"] > active[key]["ts_utc"]:
                del active[key]
                
        now = get_now_utc()
        for (ctype, target), ev in active.items():
            ttl = ev.get("details", {}).get("ttl_seconds", 0)
            if ttl <= 0: continue
            start_ts = datetime.fromisoformat(ev["ts_utc"].replace("Z", "+00:00"))
            if start_ts + timedelta(seconds=ttl) < now:
                self.decisions.append({"action": "expire", "type": ctype, "target": target})
                if self.confirmed and self.env_enabled and not self.replay_mode:
                    self.emit_event("consequence_expired", {
                        "consequence_type": ctype, "target": target, "rule_id": ev.get("details", {}).get("rule_id")
                    })

    def run_loop(self):
        # 0. Tick
        self.emit_event("sovereign_tick", {
            "run_id": self.run_id,
            "policy_sha": self.policy_sha,
            "engine_sha": self.engine_sha
        })

        # 1. Reconcile
        self.reconcile()

        # 2. Evaluate
        for rule in self.consequence_policy.get("rules", []):
            match = rule.get("match", {})
            cond = rule.get("condition", {})
            triggers = self.run_query(match.get("action"), last_min=cond.get("duration_minutes", 10))
            if "level" in match:
                triggers = [t for t in triggers if t.get("level") == match["level"]]
            
            if len(triggers) >= cond.get("min_events", 1):
                self.triggers_found.append(rule["id"])
                for cons in rule.get("consequences", []):
                    ctype, target = cons.get("type"), cons.get("target")
                    if ctype not in ALLOWED_ACTIONS or target not in ALLOWED_TARGETS: continue
                    
                    if self.check_rate_limits(ctype):
                        self.decisions.append({"action": "engage", "type": ctype, "target": target, "rule_id": rule["id"]})
                        if self.confirmed and self.env_enabled and not self.replay_mode:
                            self.emit_event("consequence_engaged", {
                                "consequence_type": ctype, "target": target,
                                "details": {"ttl_seconds": cons.get("ttl_seconds", 0), "rule_id": rule["id"]}
                            })
                    else:
                        self.decisions.append({"action": "rate_limited", "type": ctype, "target": target, "rule_id": rule["id"]})

        # 3. Audit Bundle
        self.save_audit()

    def save_audit(self):
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        bundle = {
            "run_id": self.run_id,
            "ts_utc": get_now_utc().isoformat(),
            "flags": {"confirmed": self.confirmed, "env_enabled": self.env_enabled, "replay": self.replay_mode},
            "triggers": self.triggers_found,
            "decisions": self.decisions,
            "shas": {"policy": self.policy_sha, "engine": self.engine_sha}
        }
        audit_file = AUDIT_DIR / f"{get_now_utc().strftime('%Y%m%dT%H%M%SZ')}_{self.run_id}.json"
        with open(audit_file, "w") as f:
            json.dump(bundle, f, indent=2)
        print(f"Audit bundle saved: {audit_file.name}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args()
    
    # Fail-closed check
    if not INDEX_DIR.exists() or not QUERY_TOOL.exists():
        print("CRITICAL: Index or query tool missing. Fail-closed.")
        sys.exit(1)
        
    ctrl = SovereignControl(confirmed=args.confirmed)
    ctrl.run_loop()

if __name__ == "__main__":
    main()
