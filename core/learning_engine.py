import json
from pathlib import Path
from collections import defaultdict
from core.config import RUNTIME_LOGS_DIR

TRACE_FILE = RUNTIME_LOGS_DIR / "activity_feed.jsonl"


def analyze_patterns(min_frequency: int = 3):

    if not TRACE_FILE.exists():
        return {
            "status": "no_data",
            "candidates": [],
        }

    counter = defaultdict(int)

    with open(TRACE_FILE, "r") as f:
        for line in f:
            try:
                trace = json.loads(line)

                if trace.get("result", {}).get("status") != "success":
                    continue

                cmd = trace.get("command", {})
                key = f"{cmd.get('name')} {' '.join(cmd.get('args', []))}"

                counter[key] += 1

            except Exception:
                continue

    candidates = [
        {"command": k, "frequency": v}
        for k, v in counter.items()
        if v >= min_frequency
    ]

    return {
        "status": "ok",
        "candidates": candidates,
        "total_unique": len(counter),
    }
