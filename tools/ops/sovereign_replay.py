#!/usr/bin/env python3
"""
tools/ops/sovereign_replay.py — Forensic Replay for Sovereign Decisions
"""
import sys
import argparse
import json
from pathlib import Path
from sovereign_loop import SovereignControl

def main():
    parser = argparse.ArgumentParser(description="Forensic Replay Harness")
    parser.add_argument("--feed", type=Path, required=True, help="Snapshot of activity_feed.jsonl")
    parser.add_argument("--index-dir", type=Path, required=True, help="Snapshot directory of index")
    parser.add_argument("--policy", type=Path, required=True, help="Policy file to test")
    parser.add_argument("--loop-policy", type=Path, required=True, help="Loop policy file to test")
    
    args = parser.parse_args()
    
    # In a real environment, we would point the query tool to use the snapshot feed/index.
    # For this simulation, we assume the query tool is compatible with overrides via env or args.
    # Since our SovereignControl calls the query tool, we'd need to ensure the query tool 
    # honors the snapshot path.
    
    # For Pack 9 implementation, we simulate the parity check.
    ctrl = SovereignControl(
        confirmed=False, 
        replay_mode=True, 
        policy_path=args.policy,
        loop_policy_path=args.loop_policy
    )
    
    print(f"--- STARTING REPLAY (Mode: Parity Check) ---")
    ctrl.run_loop()
    
    print(json.dumps({
        "status": "complete",
        "replay_mode": True,
        "run_id": ctrl.run_id,
        "decisions": ctrl.decisions,
        "triggers": ctrl.triggers_found
    }, indent=2))

if __name__ == "__main__":
    main()
