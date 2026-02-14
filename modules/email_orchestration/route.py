from __future__ import annotations

from typing import Any, Dict


def route_task(parsed: Dict[str, Any], request_channel: str) -> Dict[str, Any]:
    ring = str(parsed.get("ring", "")).upper()
    lane = parsed.get("lane")
    if not lane:
        lane = {
            "R0": "observe",
            "R1": "assist",
            "R2": "execute",
            "R3": "governed",
        }.get(ring, "")
    response_channel = f"gg:responses:{parsed.get('task_id','unknown')}"
    return {
        "ring": ring,
        "lane": lane,
        "request_channel": request_channel,
        "response_channel": response_channel,
    }
