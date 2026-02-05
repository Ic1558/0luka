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
import os
from functools import lru_cache
import yaml
from core.enforcement import RuntimeEnforcer

# Single SOT path for policy
RUNTIME_POLICY_PATH = os.getenv(
    "OPAL_RUNTIME_POLICY_PATH",
    os.path.join("core", "runtime_policy.yaml"),
)

@lru_cache(maxsize=1)
def _load_runtime_policy() -> dict:
    with open(RUNTIME_POLICY_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

@lru_cache(maxsize=1)
def _enforcer() -> RuntimeEnforcer:
    return RuntimeEnforcer.load_policy() # Use class method from implementation or adapt

# Adapter for user's patch to match my implementation
# My implementation in enforcement.py uses class methods directly, 
# but the user's patch uses instance. I will adapt to use my implementation's style
# which was: RuntimeEnforcer.enforce_context(role, payload)

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

    # ═══════════════════════════════════════════
    # ORCHESTRATOR CONTEXT GATE
    # ═══════════════════════════════════════════
    # Intercepts user-provided raw_input BEFORE it becomes an Intent/TaskSpec.
    try:
        payload = {"raw_input": raw_input}
        # Using class method as defined in my core/enforcement.py
        gated = RuntimeEnforcer.enforce_context(
            role="orchestrator",
            payload=payload,
        )
        # Check if gated payload modified the input (truncation)
        if gated.get("raw_input") != raw_input:
             # If truncated, use the safe version
             text = gated["raw_input"].strip().lower()
             
    except Exception as e:
        # Hard Deny
        print(f"[Context Gate] VIOLATION: {e}")
        return {
            "intent": "violation",
            "tool": "denied",
            "risk": "critical",
            "params": {"error": str(e)},
            "matched_pattern": None
        }
    # ═══════════════════════════════════════════

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
