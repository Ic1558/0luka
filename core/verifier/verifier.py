"""AG-19: Verifier — reads artifacts and activity feed to verify an execution.

The verifier is STRICTLY READ-ONLY. It never:
  - dispatches tasks
  - writes to action queues
  - mutates runtime state

Possible statuses: SUCCESS | FAILED | PARTIAL
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


def _verification_id(run_id: str, execution_id: str, ts: str) -> str:
    raw = f"{run_id}|{execution_id}|{ts}"
    return "vrfy_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _activity_events_for_run(run_id: str) -> list[dict[str, Any]]:
    """Read activity feed for events matching run_id (read-only)."""
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        return []
    feed = Path(runtime_root) / "logs" / "activity_feed.jsonl"
    if not feed.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        for line in feed.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
                # D-2 sovereign seal: only admit runtime evidence for verdict logic.
                # Records missing emit_mode or with non-runtime provenance are excluded.
                if (isinstance(e, dict)
                        and str(e.get("task_id") or "") == run_id
                        and e.get("emit_mode") == "runtime_auto"):
                    events.append(e)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return events


def _classify_execution(execution_result: dict[str, Any]) -> str:
    """Derive SUCCESS/FAILED/PARTIAL from execution result."""
    status = str(execution_result.get("status") or "").upper()
    if status == "NO_OP":
        return "SUCCESS"
    if status == "SUCCESS":
        return "SUCCESS"
    if status == "FAILED":
        return "FAILED"
    executed = execution_result.get("executed_steps") or []
    if not executed:
        return "FAILED"
    ok_count = sum(1 for s in executed if s.get("ok"))
    if ok_count == len(executed):
        return "SUCCESS"
    if ok_count == 0:
        return "FAILED"
    return "PARTIAL"


def verify_execution(
    run_id: str,
    execution_result: dict[str, Any],
) -> dict[str, Any]:
    """Verify the outcome of an execution against runtime evidence.

    Args:
        run_id:           The task/run being verified.
        execution_result: Result dict from executor.execute_plan().

    Returns:
        Verification result with: verification_id, run_id, execution_id,
        status (SUCCESS/FAILED/PARTIAL), verified_at, reason.
    """
    verified_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    verification_id = _verification_id(
        run_id,
        str(execution_result.get("execution_id") or ""),
        verified_at,
    )

    # Derive status from execution result
    status = _classify_execution(execution_result)

    # Cross-check activity feed: look for dispatch.end event
    activity_events = _activity_events_for_run(run_id)
    dispatch_ends = [e for e in activity_events if e.get("event") == "dispatch.end"]

    # If executor submitted a retry and we found a dispatch end for it, upgrade PARTIAL→SUCCESS
    executed_steps = execution_result.get("executed_steps") or []
    retry_task_ids = [
        s.get("task_id")
        for s in executed_steps
        if s.get("step") == "retry_task" and s.get("ok")
    ]
    if retry_task_ids and dispatch_ends:
        dispatched_ids = {str(e.get("task_id") or "") for e in dispatch_ends}
        if any(tid in dispatched_ids for tid in retry_task_ids if tid):
            status = "SUCCESS"

    reason = f"execution_status={execution_result.get('status', 'unknown')}"
    if status == "SUCCESS":
        reason = "all_steps_passed"
    elif status == "PARTIAL":
        ok = sum(1 for s in executed_steps if s.get("ok"))
        total = len(executed_steps)
        reason = f"{ok}/{total}_steps_passed"

    # AG-28: structured failure context for recovery engine
    failure_type = _classify_failure_type(status, execution_result)
    recoverable = status in ("FAILED", "PARTIAL") and failure_type not in (
        "protected_zone_violation", "emergency_stop_triggered",
        "topology_lockdown", "process_concurrency_conflict", "policy_block",
    )

    return {
        "verification_id": verification_id,
        "run_id": run_id,
        "execution_id": str(execution_result.get("execution_id") or ""),
        "status": status,
        "verified_at": verified_at,
        "reason": reason,
        # AG-28 recovery context fields
        "failure_type": failure_type,
        "recoverable": recoverable,
        "requires_operator": not recoverable and status != "SUCCESS",
        "protected_zone_related": failure_type == "protected_zone_violation",
        "topology_sensitive": failure_type in ("topology_lockdown", "topology_unstable"),
    }


def _classify_failure_type(status: str, execution_result: dict[str, Any]) -> str:
    """Classify failure type for recovery engine consumption."""
    if status == "SUCCESS":
        return "none"

    # Check explicit failure tags from executor
    tags = execution_result.get("failure_tags") or []
    if "protected_zone" in tags:
        return "protected_zone_violation"
    if "emergency_stop" in tags:
        return "emergency_stop_triggered"
    if "topology" in tags:
        return "topology_lockdown"
    if "process_conflict" in tags:
        return "process_concurrency_conflict"
    if "policy_block" in tags:
        return "policy_block"
    if "missing_artifact" in tags:
        return "missing_artifact"
    if "artifact_mismatch" in tags:
        return "artifact_mismatch"

    exec_status = str(execution_result.get("status") or "").upper()
    if exec_status in ("FAILED", "ERROR"):
        return "execution_failed"
    if status == "PARTIAL":
        return "verification_failed"
    return "verification_failed"
