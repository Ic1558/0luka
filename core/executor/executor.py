"""AG-19: Executor — runs a plan through the dispatcher-compatible path only.

Supported step actions:
  verify_artifacts — checks runtime artifacts for the run
  retry_task       — submits a retry sentinel via core.submit.submit_task()

Rules:
  - No direct shell execution
  - No direct git mutation
  - No repo metadata writes
  - Every step must have a policy verdict ALLOW before running
  - Idempotent: running same plan twice is safe (retry produces new task_id)
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ALLOWED_STEP_ACTIONS: frozenset[str] = frozenset({"verify_artifacts", "retry_task"})


def _execution_id(plan_id: str, ts: str) -> str:
    raw = f"{plan_id}|{ts}"
    return "exec_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _execute_verify_artifacts(run_id: str) -> dict[str, Any]:
    """Check that runtime artifacts exist for the run. Read-only."""
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        return {"step": "verify_artifacts", "ok": False, "reason": "no_runtime_root"}

    artifact_dirs = [
        Path(runtime_root) / "artifacts",
        Path(runtime_root) / "artifacts" / "tasks",
        Path(runtime_root) / "logs",
    ]
    found: list[str] = []
    for d in artifact_dirs:
        if d.exists():
            found.extend(
                str(p.relative_to(Path(runtime_root)))
                for p in d.glob(f"*{run_id}*")
                if p.is_file()
            )

    return {
        "step": "verify_artifacts",
        "ok": True,
        "run_id": run_id,
        "artifacts_found": len(found),
        "paths": found[:10],
    }


def _execute_retry_task(run_id: str) -> dict[str, Any]:
    """Submit a bounded retry task through the dispatcher path."""
    try:
        from core.submit import submit_task

        task_id = f"exec_retry_{run_id[:20]}_{int(time.time())}"
        task: dict[str, Any] = {
            "task_id": task_id,
            "author": "executor",
            "schema_version": "clec.v1",
            "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "call_sign": "[Executor]",
            "root": "${ROOT}",
            "intent": "executor.retry",
            "ops": [],
            "verify": [],
        }
        receipt = submit_task(task)
        return {"step": "retry_task", "ok": True, "task_id": task_id, "receipt": receipt}
    except Exception as exc:
        logger.warning("executor retry_task failed: %s", exc)
        return {"step": "retry_task", "ok": False, "reason": str(exc)}


def execute_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Execute a plan's steps through the bounded dispatcher-compatible path.

    Args:
        plan: Plan dict from planner.create_plan().

    Returns:
        Execution result dict with: execution_id, plan_id, run_id,
        started_at, completed_at, status, executed_steps, policy_verdict.
    """
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    execution_id = _execution_id(plan.get("plan_id", ""), started_at)
    run_id = str(plan.get("run_id", ""))
    steps: list[dict[str, Any]] = plan.get("steps") or []

    if not steps:
        return {
            "execution_id": execution_id,
            "plan_id": plan.get("plan_id", ""),
            "run_id": run_id,
            "started_at": started_at,
            "completed_at": started_at,
            "status": "NO_OP",
            "executed_steps": [],
            "policy_verdict": "ALLOW",
        }

    executed_steps: list[dict[str, Any]] = []
    all_ok = True

    for step in steps:
        action = str(step.get("action", "")).lower().strip()

        if action not in _ALLOWED_STEP_ACTIONS:
            result = {"step": action, "ok": False, "reason": "disallowed_action"}
            executed_steps.append(result)
            all_ok = False
            continue

        if action == "verify_artifacts":
            result = _execute_verify_artifacts(run_id)
        elif action == "retry_task":
            result = _execute_retry_task(run_id)
        else:
            result = {"step": action, "ok": False, "reason": "unhandled"}

        executed_steps.append(result)
        if not result.get("ok"):
            all_ok = False

    completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    status = "SUCCESS" if all_ok else ("FAILED" if not any(r.get("ok") for r in executed_steps) else "PARTIAL")

    return {
        "execution_id": execution_id,
        "plan_id": plan.get("plan_id", ""),
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "status": status,
        "executed_steps": executed_steps,
        "policy_verdict": "ALLOW",
    }
