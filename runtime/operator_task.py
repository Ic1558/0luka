"""AG-P4/P8: Operator Task Entry — governed inference + planning submission.

Path:
  submit_operator_task(prompt, operator_id, provider, plan_steps)
    → generate task_id
    → approval gate (task_execution lane, fail-closed)
    → route_inference(prompt, provider)
    → generate_plan(task_id, inference_result, plan_steps)
    → validate_plan  (kernel BLOCK check + operator whitelist)
    → execute_operator_plan (dispatch allowed steps)
    → write governed evidence record
    → return result

AG-P8: plan_steps enables structured multi-step execution.
       If plan_steps is None, a default no_op plan is generated.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write(path: Path, data: dict) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _check_approval() -> tuple[bool, str]:
    """Check task_execution lane approval. Returns (approved, reason)."""
    try:
        from tools.ops.approval_state import load_approval_state
        state = load_approval_state()
        lane = state["lanes"].get("task_execution", {})
        if lane.get("approved_effective"):
            return True, "approved"
        reason = "approval_expired" if lane.get("expired") else "approval_missing"
        return False, reason
    except Exception as exc:
        return False, f"approval_check_error:{exc}"


def submit_operator_task(
    prompt: str,
    operator_id: str = "system",
    provider: str = "claude",
    plan_steps: list | None = None,
) -> dict:
    """Submit an operator task through governed inference + planning path.

    Args:
        prompt:     Natural language task prompt.
        operator_id: Caller identity.
        provider:   Inference provider (default: claude).
        plan_steps: Optional explicit step list. Each step:
                    {"action": "tool_dispatch", "tool": "...", "params": {...}}
                    If None, a default no_op plan is generated.

    Returns a result dict always. Never raises — errors recorded in result.
    """
    task_id = f"op_{uuid.uuid4().hex[:12]}_{int(time.time())}"
    ts = _now()
    sd = _state_dir()

    # Step 1: approval gate
    approved, approval_reason = _check_approval()
    if not approved:
        record = {
            "task_id": task_id,
            "operator_id": operator_id,
            "provider": provider,
            "prompt_len": len(prompt),
            "ts_submitted": ts,
            "status": "blocked",
            "block_reason": approval_reason,
            "inference_id": None,
            "request_id": None,
            "response": None,
            "plan": None,
            "execution": None,
            "governed": True,
        }
        _append_jsonl(sd / "operator_task_log.jsonl", record)
        return record

    # Step 2: governed inference
    inf: dict = {}
    try:
        from runtime.governed_inference import route_inference
        inf = route_inference(prompt, preferred_provider=provider, operator_id=operator_id)
    except Exception as exc:
        record = {
            "task_id": task_id,
            "operator_id": operator_id,
            "provider": provider,
            "prompt_len": len(prompt),
            "ts_submitted": ts,
            "status": "error",
            "block_reason": str(exc),
            "inference_id": None,
            "request_id": None,
            "response": None,
            "plan": None,
            "execution": None,
            "governed": True,
        }
        _append_jsonl(sd / "operator_task_log.jsonl", record)
        _atomic_write(sd / "operator_task_latest.json", record)
        return record

    # Step 3: generate → validate → execute plan (AG-P8)
    plan: dict = {}
    execution: dict = {}
    plan_verdict = "ALLOW"
    try:
        from runtime.operator_planner import (
            generate_plan,
            validate_plan,
            execute_operator_plan,
            write_plan_evidence,
        )
        plan = generate_plan(
            task_id,
            operator_id,
            inf["inference_id"],
            inf.get("response"),
            prompt,
            plan_steps=plan_steps,
        )
        plan_verdict, validation_reason = validate_plan(plan)
        plan["policy_verdict"] = plan_verdict
        plan["validation_reason"] = validation_reason

        if plan_verdict == "ALLOW":
            execution = execute_operator_plan(plan, operator_id=operator_id)
        else:
            execution = {"execution_status": "BLOCKED", "executed_steps": [], "reason": validation_reason}

        write_plan_evidence(plan, execution)
    except Exception as exc:
        plan_verdict = "error"
        execution = {"execution_status": "error", "error": str(exc)}

    record = {
        "task_id": task_id,
        "operator_id": operator_id,
        "provider": inf.get("provider", provider),
        "prompt_len": len(prompt),
        "ts_submitted": ts,
        "status": "executed" if plan_verdict == "ALLOW" else "plan_blocked",
        "block_reason": None if plan_verdict == "ALLOW" else plan.get("validation_reason"),
        "inference_id": inf.get("inference_id"),
        "request_id": inf.get("request_id"),
        "response": inf.get("response"),
        "governed": inf.get("governed", True),
        "ts_executed": inf.get("ts_routed"),
        "plan_id": plan.get("plan_id"),
        "plan_verdict": plan_verdict,
        "execution_status": execution.get("execution_status"),
    }

    _append_jsonl(sd / "operator_task_log.jsonl", record)
    _atomic_write(sd / "operator_task_latest.json", record)
    return record
