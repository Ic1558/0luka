"""
NLP Normalizer (Rule-based v1)
==============================
Convert natural language to structured TaskSpec.

COPY EXACT from tools/web_bridge/routers/chat.py lines 67-126
"""

from datetime import datetime, timezone
from typing import Dict, Any
import uuid
import re

# ============================================================
# Intent Pattern Matching
# ============================================================

INTENT_PATTERNS = [
    # Pattern, intent, tool, risk
    (r"^(liam\s+)?(check|show|get)\s+status$", "status_check", "status_reader", "low"),
    (r"^(liam\s+)?session\s+(start|begin)", "session_start", "session_manager", "low"),
    (r"^(show|list)\s+(tasks?|pending|inbox)", "task_list", "inbox_reader", "low"),
    (r"^(liam\s+)?plan\s+", "planning", "planner", "low"),
    (r"^(lisa\s+)?(run|execute)\s+", "task_execution", "task_runner", "high"),
    (r"^(vera\s+)?(verify|audit|check)\s+", "verification", "verifier", "low"),
]

def normalize_input(raw_input: str) -> Dict[str, Any]:
    """
    Convert natural language to structured TaskSpec.

    NO EXECUTION - only parsing and structuring.
    """
    text = raw_input.strip().lower()

    for pattern, intent, tool, risk in INTENT_PATTERNS:
        if re.match(pattern, text):
            return {
                "intent": intent,
                "tool": tool,
                "risk": risk,
                "params": {"raw": raw_input},
                "matched_pattern": pattern
            }

    # Fallback: unknown
    return {
        "intent": "unknown",
        "tool": "unknown",
        "risk": "high",
        "params": {"raw": raw_input},
        "matched_pattern": None
    }

def build_task_spec(normalized: Dict[str, Any], preview_id: str) -> Dict[str, Any]:
    """Build a TaskSpec v2 compatible structure."""
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")
    rand = uuid.uuid4().hex[:6]
    task_id = f"task_{ts}_{rand}"

    return {
        "task_id": task_id,
        "author": "gmx",  # Server-enforced
        "intent": normalized["intent"],
        "operations": [{
            "id": "op_1",
            "tool": normalized["tool"],
            "params": normalized["params"],
            "risk_hint": normalized["risk"]
        }],
        "created_at_utc": now.isoformat().replace("+00:00", "Z"),
        "lane": "approval" if normalized["risk"] == "high" else "task",
        "reply_to": "interface/outbox/tasks",
        "preview_id": preview_id
    }
