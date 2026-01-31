#!/usr/bin/env python3
import json
import argparse
import subprocess
import time
from pathlib import Path
from _base_agent import BaseAgent

class LisaExecutor(BaseAgent):
    CALL_SIGN = "[Lisa]"
    AGENT_NAME = "lisa"
    MODE = "executor"

    def __init__(self):
        super().__init__()
        # Dynamic Root resolution
        self.ALLOW_WRITE_PATHS = [
            self.ROOT / "tools",
            self.ROOT / "interface",
            self.ROOT / "modules",
            self.ROOT / "system",
        ]

    ALLOW_COMMANDS = {
        "echo",
        "sed",
        "grep",
        "python3",
        "cat",
        "ls",
        "date",
    }

    def run(self, task_path: Path):
        self.enforce_call_sign()

        if not task_path.exists():
            self._panic(f"Task input missing: {task_path}")

        try:
            task = json.loads(task_path.read_text())
        except Exception as e:
            self._panic(f"Failed to parse Task JSON: {e}")

        ops = task.get("ops", [])
        task_id = task.get("task_id", "TASK-UNKNOWN")

        timeline = []
        for op in ops:
            cmd = op.get("cmd")
            if not cmd:
                self._panic("Missing cmd in op")

            binary = cmd.split()[0]
            if binary not in self.ALLOW_COMMANDS:
                self._panic(f"Command not allowlisted: {binary}")

            print(f"[{self.CALL_SIGN}] Executing: {cmd}")
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )

            timeline.append({
                "cmd": cmd,
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-2000:],
            })

            if result.returncode != 0:
                self._panic(f"Command failed: {cmd}")

        evidence = {
            "task_id": task_id,
            "timeline": timeline,
            "ts_done": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        evidence_dir = self.ROOT / "interface" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        out = evidence_dir / f"{task_id}.json"
        
        self.write_file(out, json.dumps(evidence, indent=2))

        self.log_json({
            "event": "EXECUTION_DONE",
            "task_id": task_id,
            "evidence": str(out),
        })

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, help="TaskSpec JSON")
    args = p.parse_args()

    LisaExecutor().run(Path(args.task))
import time
