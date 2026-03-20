"""
system_ops/handler.py — System operations skill handler.
"""

import os
import shutil


def execute(task: dict, context: dict) -> dict:
    """
    Execute a system_ops capability.

    Supported capabilities:
      - health_check: basic system health indicators
      - list_processes: process count estimate
      - disk_usage: disk usage for a path
      - memory_info: memory info from /proc or platform

    Returns:
      {"status": "success|error", "skill_id": "system_ops", "output": any, "trace_payload": dict}
    """
    capability = task.get("capability")
    path = task.get("path", "/")

    trace_payload = {
        "skill_id": "system_ops",
        "capability": capability,
    }

    if capability == "health_check":
        try:
            total, used, free = shutil.disk_usage("/")
            info = {
                "disk_total_gb": round(total / (1024 ** 3), 2),
                "disk_used_gb": round(used / (1024 ** 3), 2),
                "disk_free_gb": round(free / (1024 ** 3), 2),
                "load_avg": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
            }
            return {
                "status": "success",
                "skill_id": "system_ops",
                "output": info,
                "trace_payload": trace_payload,
            }
        except Exception as e:
            return {
                "status": "error",
                "skill_id": "system_ops",
                "output": None,
                "error": str(e),
                "trace_payload": trace_payload,
            }

    elif capability == "disk_usage":
        try:
            expanded = os.path.expanduser(path)
            total, used, free = shutil.disk_usage(expanded)
            info = {
                "path": path,
                "total_gb": round(total / (1024 ** 3), 2),
                "used_gb": round(used / (1024 ** 3), 2),
                "free_gb": round(free / (1024 ** 3), 2),
            }
            return {
                "status": "success",
                "skill_id": "system_ops",
                "output": info,
                "trace_payload": trace_payload,
            }
        except Exception as e:
            return {
                "status": "error",
                "skill_id": "system_ops",
                "output": None,
                "error": str(e),
                "trace_payload": trace_payload,
            }

    elif capability == "list_processes":
        try:
            import subprocess
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
            lines = result.stdout.strip().splitlines()
            return {
                "status": "success",
                "skill_id": "system_ops",
                "output": {"process_count": len(lines) - 1},
                "trace_payload": trace_payload,
            }
        except Exception as e:
            return {
                "status": "error",
                "skill_id": "system_ops",
                "output": None,
                "error": str(e),
                "trace_payload": trace_payload,
            }

    elif capability == "memory_info":
        try:
            import subprocess
            result = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5)
            output = result.stdout.strip() if result.returncode == 0 else "unavailable"
            return {
                "status": "success",
                "skill_id": "system_ops",
                "output": {"memory_stat": output[:500]},
                "trace_payload": trace_payload,
            }
        except Exception as e:
            return {
                "status": "error",
                "skill_id": "system_ops",
                "output": None,
                "error": str(e),
                "trace_payload": trace_payload,
            }

    else:
        return {
            "status": "error",
            "skill_id": "system_ops",
            "output": None,
            "error": f"unknown capability: '{capability}'",
            "trace_payload": trace_payload,
        }
