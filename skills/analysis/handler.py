"""
analysis/handler.py — Analysis skill handler.
"""

import json
import os


def execute(task: dict, context: dict) -> dict:
    """
    Execute an analysis capability.

    Supported capabilities:
      - summarize_file: return first 20 lines of a text file
      - count_lines: count lines in a file
      - inspect_json: parse and summarize a JSON file

    Returns:
      {"status": "success|error", "skill_id": "analysis", "output": any, "trace_payload": dict}
    """
    capability = task.get("capability")
    path = task.get("path", ".")

    trace_payload = {
        "skill_id": "analysis",
        "capability": capability,
        "path": path,
    }

    if capability == "summarize_file":
        try:
            expanded = os.path.expanduser(path)
            with open(expanded, "r") as f:
                lines = f.readlines()
            preview = "".join(lines[:20])
            return {
                "status": "success",
                "skill_id": "analysis",
                "output": {
                    "total_lines": len(lines),
                    "preview": preview,
                },
                "trace_payload": trace_payload,
            }
        except Exception as e:
            return {
                "status": "error",
                "skill_id": "analysis",
                "output": None,
                "error": str(e),
                "trace_payload": trace_payload,
            }

    elif capability == "count_lines":
        try:
            expanded = os.path.expanduser(path)
            with open(expanded, "r") as f:
                count = sum(1 for _ in f)
            return {
                "status": "success",
                "skill_id": "analysis",
                "output": {"line_count": count, "path": path},
                "trace_payload": trace_payload,
            }
        except Exception as e:
            return {
                "status": "error",
                "skill_id": "analysis",
                "output": None,
                "error": str(e),
                "trace_payload": trace_payload,
            }

    elif capability == "inspect_json":
        try:
            expanded = os.path.expanduser(path)
            with open(expanded, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                summary = {"type": "object", "top_level_keys": list(data.keys())[:20]}
            elif isinstance(data, list):
                summary = {"type": "array", "length": len(data)}
            else:
                summary = {"type": type(data).__name__}
            return {
                "status": "success",
                "skill_id": "analysis",
                "output": summary,
                "trace_payload": trace_payload,
            }
        except Exception as e:
            return {
                "status": "error",
                "skill_id": "analysis",
                "output": None,
                "error": str(e),
                "trace_payload": trace_payload,
            }

    else:
        return {
            "status": "error",
            "skill_id": "analysis",
            "output": None,
            "error": f"unknown capability: '{capability}'",
            "trace_payload": trace_payload,
        }
