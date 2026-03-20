"""
agent_dispatch_bridge.py — Generates structured dispatch payloads for agent routing.

Invariants:
  - No live dispatch — payload generation only in this phase
  - No bypass of skills/safety/hindsight/failure-memory protections
  - review_required=True for any non-success result
  - dispatch_ready=False for rejected/blocked/failed results

Output contract:
  {
    "target_agent": str,
    "task_summary": str,
    "source_trace_id": str | None,
    "review_required": bool,
    "dispatch_ready": bool,
    "payload_id": str,
  }
"""

import uuid

_SUPPORTED_AGENTS = {"clc", "codex", "mary", "liam", "lisa", "system"}

_AGENT_FOR_STATUS = {
    "success": "codex",
    "planned": "codex",
    "rejected": "clc",
    "blocked": "clc",
    "failed": "clc",
}


def create_dispatch_payload(result: dict, target_agent: str = None) -> dict:
    """
    Generate a structured dispatch payload from an execution result.

    Args:
        result: Execution result dict. Accepts orchestrator output or CLI output.
                Must contain at least "status". May contain "trace_id", "intent",
                "reason", "normalized_task".
        target_agent: Optional agent override. Auto-selected from status if None.

    Returns:
        Structured dispatch payload.
    """
    # extract status — support both flat and nested result
    inner = result.get("result") or {}
    status = result.get("status") or inner.get("status", "unknown")
    reason = result.get("reason") or inner.get("reason", "")

    # extract trace_id
    trace_id = (
        result.get("trace_id")
        or inner.get("trace_id")
    )

    # extract intent / summary
    intent = (
        result.get("intent")
        or (result.get("normalized_task") or {}).get("intent")
        or "unknown task"
    )
    task_summary = f"{status}: {intent[:120]}"
    if reason:
        task_summary += f" [{reason}]"

    # agent selection
    if target_agent and target_agent in _SUPPORTED_AGENTS:
        selected_agent = target_agent
    else:
        selected_agent = _AGENT_FOR_STATUS.get(status, "clc")

    review_required = status not in ("success", "planned")
    dispatch_ready = status in ("success", "planned")

    return {
        "target_agent": selected_agent,
        "task_summary": task_summary,
        "source_trace_id": trace_id,
        "review_required": review_required,
        "dispatch_ready": dispatch_ready,
        "payload_id": str(uuid.uuid4())[:8],
    }
