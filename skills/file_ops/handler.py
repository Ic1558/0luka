"""
file_ops/handler.py — File system operations skill handler.
"""

import os
import uuid
from datetime import datetime, timezone


def execute(task: dict, context: dict) -> dict:
    """
    Execute a file_ops capability.

    Supported capabilities:
      - list_files: list files/dirs in given path
      - read_file: read contents of a file
      - file_info: stat info for a path

    Returns:
      {"status": "success|error", "skill_id": "file_ops", "output": any, "trace_payload": dict}
    """
    capability = task.get("capability")
    path = task.get("path", ".")

    trace_payload = {
        "skill_id": "file_ops",
        "capability": capability,
        "path": path,
    }

    if capability == "list_files":
        try:
            expanded = os.path.expanduser(path)
            entries = sorted(os.listdir(expanded))
            return {
                "status": "success",
                "skill_id": "file_ops",
                "output": entries,
                "trace_payload": trace_payload,
            }
        except Exception as e:
            return {
                "status": "error",
                "skill_id": "file_ops",
                "output": None,
                "error": str(e),
                "trace_payload": trace_payload,
            }

    elif capability == "read_file":
        try:
            expanded = os.path.expanduser(path)
            with open(expanded, "r") as f:
                content = f.read()
            return {
                "status": "success",
                "skill_id": "file_ops",
                "output": content,
                "trace_payload": trace_payload,
            }
        except Exception as e:
            return {
                "status": "error",
                "skill_id": "file_ops",
                "output": None,
                "error": str(e),
                "trace_payload": trace_payload,
            }

    elif capability == "file_info":
        try:
            expanded = os.path.expanduser(path)
            stat = os.stat(expanded)
            info = {
                "path": path,
                "size": stat.st_size,
                "is_dir": os.path.isdir(expanded),
                "is_file": os.path.isfile(expanded),
            }
            return {
                "status": "success",
                "skill_id": "file_ops",
                "output": info,
                "trace_payload": trace_payload,
            }
        except Exception as e:
            return {
                "status": "error",
                "skill_id": "file_ops",
                "output": None,
                "error": str(e),
                "trace_payload": trace_payload,
            }

    else:
        return {
            "status": "error",
            "skill_id": "file_ops",
            "output": None,
            "error": f"unknown capability: '{capability}'",
            "trace_payload": trace_payload,
        }
