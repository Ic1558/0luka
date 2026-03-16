"""AG-P4: Operator Task Entry — governed inference submission for operators.

Path:
  submit_operator_task(prompt, operator_id, provider)
    → generate task_id
    → approval gate (task_execution lane, fail-closed)
    → route_inference(prompt, provider)
    → write governed evidence record
    → return result

This module is the minimum surface binding operator intent to the
governed inference fabric. It does NOT redesign feedback_loop or
provider architecture.
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
) -> dict:
    """Submit an operator task through the governed inference path.

    Returns a result dict always. Never raises — errors are recorded in result.
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
            "governed": True,
        }
        _append_jsonl(sd / "operator_task_log.jsonl", record)
        return record

    # Step 2: governed inference
    try:
        from runtime.governed_inference import route_inference
        inf = route_inference(prompt, preferred_provider=provider, operator_id=operator_id)
        record = {
            "task_id": task_id,
            "operator_id": operator_id,
            "provider": inf["provider"],
            "prompt_len": len(prompt),
            "ts_submitted": ts,
            "status": "executed",
            "block_reason": None,
            "inference_id": inf["inference_id"],
            "request_id": inf["request_id"],
            "response": inf["response"],
            "governed": inf["governed"],
            "ts_executed": inf["ts_routed"],
        }
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
            "governed": True,
        }

    _append_jsonl(sd / "operator_task_log.jsonl", record)
    _atomic_write(sd / "operator_task_latest.json", record)
    return record
