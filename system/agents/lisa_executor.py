#!/usr/bin/env python3
import json
import argparse
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Tuple

try:
    from ._base_agent import BaseAgent
except Exception:
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


def execute_task_spec(task_spec: Dict[str, Any], *, root: Path | None = None) -> Tuple[str, Dict[str, Any]]:
    """Canonical lisa execution entry for router authority path."""
    ops = task_spec.get("ops")
    if not isinstance(ops, list) or not ops:
        return "error", {"logs": ["missing_ops"], "commands": [], "effects": []}

    task_id = str(task_spec.get("task_id") or task_spec.get("id") or "unknown")
    logs: list[dict[str, Any]] = []
    commands: list[str] = []
    effects: list[str] = []
    for idx, op in enumerate(ops):
        if not isinstance(op, dict):
            return "error", {"logs": [f"invalid_op:{idx}"], "commands": commands, "effects": effects}
        if op.get("type") != "run":
            return "error", {"logs": [f"unsupported_op_type:{op.get('type')}"], "commands": commands, "effects": effects}
        command = str(op.get("command", "")).strip()
        if not command:
            return "error", {"logs": [f"empty_command:{idx}"], "commands": commands, "effects": effects}

        binary = command.split()[0]
        if binary not in LisaExecutor.ALLOW_COMMANDS:
            return "error", {"logs": [f"command_not_allowlisted:{binary}"], "commands": commands, "effects": effects}

        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
        )
        commands.append(command)
        logs.append(
            {
                "op_index": idx,
                "command": command,
                "returncode": int(proc.returncode),
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
        effects.append(f"run:{command}")
        if proc.returncode != 0:
            return "error", {"logs": logs, "commands": commands, "effects": effects, "task_id": task_id}

    return "ok", {"logs": logs, "commands": commands, "effects": effects, "task_id": task_id}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=False, help="TaskSpec JSON")
    p.add_argument("--root", required=False, help="Compatibility arg for launchd runner")
    args = p.parse_args()
    if args.task:
        LisaExecutor().run(Path(args.task))
