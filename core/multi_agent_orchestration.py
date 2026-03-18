"""
multi_agent_orchestration.py — Structured multi-agent orchestration contracts.

Invariants:
  - No live Redis publish / no fake live delivery
  - Orchestration candidates only — operator routes actual handoff
  - review_required=True for cross-agent handoffs
  - orchestration_ready=False for rejected/unknown results

Output contract:
  {
    "source_trace_id": str | None,
    "source_agent": str,
    "target_agent": str,
    "task_summary": str,
    "review_required": bool,
    "orchestration_ready": bool,
    "candidate_id": str,
  }
"""

import uuid

_KNOWN_AGENTS = {"clc", "codex", "mary", "liam", "lisa", "gmx", "vera", "system", "paula"}

_SOURCE_AGENT_FOR_MODE = {
    "plan_only": "system",
    "apply": "system",
    "verify": "vera",
}

_TARGET_FOR_STATUS = {
    "success": "codex",
    "planned": "codex",
    "rejected": "clc",
    "blocked": "clc",
    "failed": "clc",
}


def create_orchestration_candidate(
    result: dict,
    target_agent: str = None,
    source_agent: str = None,
) -> dict:
    """
    Create a structured orchestration handoff candidate.

    Args:
        result: Execution result dict (flat or nested from orchestrator/CLI).
        target_agent: Override target agent. Auto-detected from status if None.
        source_agent: Override source agent. Auto-detected from execution_mode if None.

    Returns:
        Structured orchestration candidate.
    """
    inner = result.get("result") or {}
    status = result.get("status") or inner.get("status", "unknown")
    reason = result.get("reason") or inner.get("reason", "")
    trace_id = result.get("trace_id") or inner.get("trace_id")
    intent = (
        result.get("intent")
        or (result.get("normalized_task") or {}).get("intent")
        or "unknown task"
    )
    mode = result.get("execution_mode", "plan_only")

    # resolve agents
    resolved_source = (
        source_agent if source_agent and source_agent in _KNOWN_AGENTS
        else _SOURCE_AGENT_FOR_MODE.get(mode, "system")
    )
    resolved_target = (
        target_agent if target_agent and target_agent in _KNOWN_AGENTS
        else _TARGET_FOR_STATUS.get(status, "clc")
    )

    task_summary = f"{status}: {intent[:100]}"
    if reason:
        task_summary += f" [{reason}]"

    review_required = status not in ("success", "planned")
    orchestration_ready = (
        status in ("success", "planned")
        and resolved_target in _KNOWN_AGENTS
    )

    return {
        "source_trace_id": trace_id,
        "source_agent": resolved_source,
        "target_agent": resolved_target,
        "task_summary": task_summary,
        "review_required": review_required,
        "orchestration_ready": orchestration_ready,
        "candidate_id": str(uuid.uuid4())[:8],
    }
