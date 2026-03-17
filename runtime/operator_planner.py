"""AG-P8: Operator Planning Layer — structured plan generation, validation, execution.

Runtime path:
    generate_plan(task_id, inference_result, steps)
    → validate_plan(plan)          — kernel BLOCK check + operator whitelist
    → execute_operator_plan(plan)  — dispatch allowed steps via runtime/tools/
    → evidence written

Step actions:
    Allowed  : tool_dispatch, log, no_op
    Blocked  : delete, rm_rf, wipe, kill, purge, drop, force_push, hard_reset
    Anything else → BLOCK (fail-closed whitelist)
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ──────────────────────────────────────────
# Policy constants
# ──────────────────────────────────────────

OPERATOR_ALLOWED_ACTIONS: frozenset[str] = frozenset({
    "tool_dispatch",
    "log",
    "no_op",
})

OPERATOR_BLOCKED_ACTIONS: frozenset[str] = frozenset({
    "delete", "rm_rf", "wipe", "kill", "purge",
    "drop", "force_push", "hard_reset", "quarantine_and_delete",
})


# ──────────────────────────────────────────
# State helpers
# ──────────────────────────────────────────

def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────
# Plan generation
# ──────────────────────────────────────────

def generate_plan(
    task_id: str,
    operator_id: str,
    inference_id: str,
    response: str | None,
    prompt: str,
    *,
    plan_steps: list[dict] | None = None,
) -> dict:
    """Generate a structured execution plan.

    If plan_steps is provided (explicit operator steps), use those.
    Otherwise emit a default single no_op step.

    Returns a plan dict with: plan_id, task_id, operator_id, inference_id,
    prompt_preview, created_at, status, steps, policy_verdict.
    """
    raw = f"{task_id}:{inference_id}"
    plan_id = "op_plan_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    steps: list[dict] = []
    if plan_steps:
        for i, s in enumerate(plan_steps):
            step = dict(s)
            step.setdefault("step_id", f"s{i + 1}")
            steps.append(step)
    else:
        steps = [{"step_id": "s1", "action": "no_op", "params": {}}]

    return {
        "plan_id": plan_id,
        "task_id": task_id,
        "operator_id": operator_id,
        "inference_id": inference_id,
        "prompt_preview": prompt[:120],
        "response_preview": (response or "")[:120],
        "created_at": _now(),
        "status": "CREATED",
        "steps": steps,
        "policy_verdict": None,
        "validation_reason": None,
    }


# ──────────────────────────────────────────
# Plan validation (two-layer)
# ──────────────────────────────────────────

def validate_plan(plan: dict) -> tuple[str, str]:
    """Validate a plan. Returns (verdict, reason).

    Layer 1 — kernel destructive-action check (step_allowed):
        Any step matching DESTRUCTIVE_ACTIONS → BLOCK immediately.
    Layer 2 — operator whitelist (OPERATOR_ALLOWED_ACTIONS):
        Any action not in whitelist → BLOCK (fail-closed).
    Layer 3 — tool existence check for tool_dispatch steps:
        Named tool must be registered; unknown tool → BLOCK.
    """
    steps: list[dict] = plan.get("steps") or []

    if not steps:
        return "ALLOW", "empty_plan"

    # Layer 1: kernel destructive check
    try:
        from core.policy.policy_gate import step_allowed
        for step in steps:
            kv = step_allowed(step)
            if kv == "BLOCK":
                action = step.get("action", "")
                return "BLOCK", f"kernel_blocked:{action}"
    except Exception:
        pass  # kernel unavailable — fall through to layer 2

    # Layer 2: operator whitelist (fail-closed — unknown action → BLOCK)
    for step in steps:
        action = str(step.get("action") or "").strip().lower()
        if not action:
            return "BLOCK", "step_action_missing"
        if action in OPERATOR_BLOCKED_ACTIONS:
            return "BLOCK", f"operator_blocked:{action}"
        if action not in OPERATOR_ALLOWED_ACTIONS:
            return "BLOCK", f"operator_not_whitelisted:{action}"

    # Layer 3: tool registry check for tool_dispatch steps
    try:
        from runtime.tools.bootstrap import bootstrap_tools
        from runtime.tools.registry import get_tool
        bootstrap_tools()
        for step in steps:
            if step.get("action") == "tool_dispatch":
                tool_name = step.get("tool", "")
                if not tool_name:
                    return "BLOCK", "tool_dispatch_tool_missing"
                if get_tool(tool_name) is None:
                    return "BLOCK", f"tool_not_registered:{tool_name}"
    except Exception as exc:
        return "BLOCK", f"tool_registry_check_error:{exc}"

    return "ALLOW", "ok"


# ──────────────────────────────────────────
# Plan execution
# ──────────────────────────────────────────

def execute_operator_plan(plan: dict, *, operator_id: str = "system") -> dict:
    """Execute a validated plan's steps. Returns execution summary dict.

    Only executes if policy_verdict == "ALLOW".
    Writes evidence to state/operator_plan_{latest,log}.
    """
    if plan.get("policy_verdict") != "ALLOW":
        return {
            "execution_status": "BLOCKED",
            "executed_steps": [],
            "reason": plan.get("validation_reason", "plan_not_allowed"),
        }

    steps: list[dict] = plan.get("steps") or []
    executed: list[dict] = []
    all_ok = True

    from runtime.tools.bootstrap import bootstrap_tools
    from runtime.tools.dispatcher import dispatch_tool
    bootstrap_tools()

    for step in steps:
        action = str(step.get("action") or "").lower()
        step_id = step.get("step_id", "?")

        if action == "tool_dispatch":
            r = dispatch_tool(
                step["tool"],
                step.get("params", {}),
                operator_id=operator_id,
                inference_id=plan.get("inference_id"),
            )
            ok = r.get("status") == "executed"
            executed.append({
                "step_id": step_id,
                "action": action,
                "tool": step["tool"],
                "dispatch_id": r.get("dispatch_id"),
                "result": r.get("result"),
                "ok": ok,
            })
            if not ok:
                all_ok = False

        elif action == "log":
            executed.append({
                "step_id": step_id,
                "action": "log",
                "message": step.get("params", {}).get("message", "")[:200],
                "ok": True,
            })

        elif action == "no_op":
            executed.append({"step_id": step_id, "action": "no_op", "ok": True})

        else:
            executed.append({"step_id": step_id, "action": action, "ok": False, "reason": "unhandled"})
            all_ok = False

    n_ok = sum(1 for s in executed if s.get("ok"))
    if all_ok:
        status = "SUCCESS"
    elif n_ok == 0:
        status = "FAILED"
    else:
        status = "PARTIAL"

    return {
        "execution_status": status,
        "executed_steps": executed,
        "steps_ok": n_ok,
        "steps_total": len(executed),
    }


# ──────────────────────────────────────────
# Evidence persistence
# ──────────────────────────────────────────

def write_plan_evidence(plan: dict, execution: dict) -> Path:
    """Write plan + execution evidence to state/. Returns path."""
    sd = _state_dir()
    record = {
        "plan_id": plan["plan_id"],
        "task_id": plan["task_id"],
        "operator_id": plan["operator_id"],
        "inference_id": plan["inference_id"],
        "plan": plan,
        "policy_verdict": plan.get("policy_verdict"),
        "validation_reason": plan.get("validation_reason"),
        "execution": execution,
        "governed": True,
        "ts": _now(),
    }
    _atomic_write(sd / "operator_plan_latest.json", record)
    _append_jsonl(sd / "operator_plan_log.jsonl", record)
    return sd / "operator_plan_latest.json"
