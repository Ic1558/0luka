#!/usr/bin/env python3
import json
import argparse
from pathlib import Path
from _base_agent import BaseAgent

class LiamPlanner(BaseAgent):
    CALL_SIGN = "[Liam]"
    AGENT_NAME = "liam"
    MODE = "planner"

    def __init__(self):
        super().__init__()
        # Dynamic Root resolution
        self.ALLOW_WRITE_PATHS = [
            self.ROOT / "interface" / "inbox" / "tasks"
        ]

    def run(self, spec_path: Path):
        self.enforce_call_sign()

        if not spec_path.exists():
            self._panic(f"TaskSpec input missing: {spec_path}")

        try:
            spec = json.loads(spec_path.read_text())
        except Exception as e:
            self._panic(f"Failed to parse TaskSpec JSON: {e}")

        # Minimal deterministic sanity
        if "intent" not in spec or "target_path" not in spec:
            self._panic("Invalid TaskSpec v2 (missing fields: intent/target_path)")

        task_id = spec.get('task_id', 'TASK-UNKNOWN')
        out_path = self.ALLOW_WRITE_PATHS[0] / f"{task_id}.json"
        
        self.write_file(out_path, json.dumps(spec, indent=2))

        self.log_json({
            "event": "TASKSPEC_EMITTED",
            "task_id": task_id,
            "output": str(out_path),
        })

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--spec", required=True, help="Path to TaskSpec v2 JSON")
    args = p.parse_args()

    LiamPlanner().run(Path(args.spec))
