"""
git_ops/handler.py — Git repository operations skill handler.
"""

import subprocess
import os


def execute(task: dict, context: dict) -> dict:
    """
    Execute a git_ops capability.

    Supported capabilities:
      - git_status: run git status
      - git_log: recent git log (last 10)
      - git_diff: git diff HEAD
      - git_branches: list local branches

    Returns:
      {"status": "success|error", "skill_id": "git_ops", "output": any, "trace_payload": dict}
    """
    capability = task.get("capability")
    path = task.get("path", ".")

    trace_payload = {
        "skill_id": "git_ops",
        "capability": capability,
        "path": path,
    }

    cmd_map = {
        "git_status": ["git", "status", "--short"],
        "git_log": ["git", "log", "--oneline", "-10"],
        "git_diff": ["git", "diff", "HEAD"],
        "git_branches": ["git", "branch", "--list"],
    }

    if capability not in cmd_map:
        return {
            "status": "error",
            "skill_id": "git_ops",
            "output": None,
            "error": f"unknown capability: '{capability}'",
            "trace_payload": trace_payload,
        }

    try:
        expanded = os.path.expanduser(path)
        result = subprocess.run(
            cmd_map[capability],
            capture_output=True,
            text=True,
            cwd=expanded,
            timeout=10,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            return {
                "status": "error",
                "skill_id": "git_ops",
                "output": None,
                "error": result.stderr.strip(),
                "trace_payload": trace_payload,
            }
        return {
            "status": "success",
            "skill_id": "git_ops",
            "output": output,
            "trace_payload": trace_payload,
        }
    except Exception as e:
        return {
            "status": "error",
            "skill_id": "git_ops",
            "output": None,
            "error": str(e),
            "trace_payload": trace_payload,
        }
