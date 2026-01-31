#!/usr/bin/env python3
# tools/replay_task.py
# Forensic State Machine Validator for 0luka Tasks

import json
import sys
from pathlib import Path
from typing import Any

VALID_TRANSITIONS = {
    "START": ["DISPATCHED", "PENDING"],
    "PENDING": ["DISPATCHED", "HANDOFF"],
    "HANDOFF": ["DISPATCHED"],
    "DISPATCHED": ["RUNNING", "RESULT_RECEIVED", "DROPPED"],
    "RUNNING": ["RESULT_RECEIVED", "DROPPED"],
    "RESULT_RECEIVED": ["DONE", "FAILED", "RETRY_SCHEDULED", "DEAD_LETTER", "DISPATCHED"],
    "RETRY_SCHEDULED": ["DISPATCHED"],
    "DONE": [], # Terminal
    "DEAD_LETTER": [], # Terminal
    "DROPPED": [], # Terminal
}

def replay_task(task_dir: Path) -> dict[str, Any]:
    timeline_file = task_dir / "timeline.jsonl"
    if not timeline_file.exists():
        return {"task_id": task_dir.name, "verdict": "INCONSISTENT", "reason": "timeline_missing"}

    events = []
    with timeline_file.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    if not events:
        return {"task_id": task_dir.name, "verdict": "INCONSISTENT", "reason": "timeline_empty"}

    current_state = None
    attempt = 1
    
    # Load meta for policy check if needed
    meta_path = task_dir / "meta.json"
    max_attempts = 3
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            # Search for max_attempts in inputs or default
            max_attempts = meta.get("max_attempts", 3)
        except: pass

    for i, ev in enumerate(events):
        event_name = ev.get("event")
        if not event_name:
            return {"task_id": task_dir.name, "verdict": "INCONSISTENT", "reason": f"missing_event_field_at_index_{i}"}

        # First event must be START or PENDING (backward compat)
        if current_state is None:
            if event_name not in ["START", "PENDING"]:
                return {"task_id": task_dir.name, "verdict": "INCONSISTENT", "reason": f"invalid_initial_state:{event_name}"}
            current_state = event_name
            continue

        # Check transition
        if event_name not in VALID_TRANSITIONS.get(current_state, []):
            # Special case: RESULT_RECEIVED implies transition but bridge might skip explicit status events
            # We allow RESULT_RECEIVED to transition to terminal states even if not explicit in timeline
            # but rule said "Deterministic", so we should be strict or handle "implied" transitions.
            return {
                "task_id": task_dir.name, 
                "verdict": "INCONSISTENT", 
                "reason": f"invalid_transition:{current_state}->{event_name}",
                "index": i
            }

        # Policy checks
        if event_name == "RETRY_SCHEDULED":
            attempt = ev.get("attempt", attempt)
            if attempt > max_attempts:
                return {"task_id": task_dir.name, "verdict": "INCONSISTENT", "reason": f"excessive_retries:{attempt}>{max_attempts}"}

        current_state = event_name

    return {
        "task_id": task_dir.name,
        "verdict": "CONSISTENT",
        "final_state": current_state,
        "events_count": len(events)
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: replay_task.py <task_dir_path>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.is_dir():
        print(f"Error: {path} is not a directory")
        sys.exit(1)

    res = replay_task(path)
    print(json.dumps(res, indent=2))
    if res["verdict"] == "INCONSISTENT":
        sys.exit(1)

if __name__ == "__main__":
    main()
