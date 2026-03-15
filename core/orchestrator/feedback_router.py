"""AG-18: Feedback router — pure routing layer between policy verdict and target.

Responsibility: given a verdict, route the decision to the correct destination.

  ALLOW    → submit bounded task to dispatcher
  BLOCK    → write block record to activity feed + halt (no dispatch)
  ESCALATE → enqueue to operator_inbox.jsonl

This component does NOT classify or evaluate policy. It only routes.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from core.decision.models import DecisionRecord
from core.operator.operator_queue import enqueue_operator_case

logger = logging.getLogger(__name__)

_ALLOWED_DISPATCH_ACTIONS = frozenset({"retry", "no_action", "nominal"})


def _submit_to_dispatcher(decision: DecisionRecord) -> dict[str, Any]:
    """Submit a bounded task through the dispatcher path only.

    Only 'retry' generates a real task. All other ALLOW verdicts are no-ops.
    """
    action = decision.action.strip().lower()
    if action != "retry":
        return {"dispatched": False, "reason": "no_op", "action": decision.action}

    try:
        from core.submit import submit_task

        task_id = f"fbr_retry_{decision.source_run_id[:20]}_{int(time.time())}"
        task: dict[str, Any] = {
            "task_id": task_id,
            "author": "feedback_router",
            "schema_version": "clec.v1",
            "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "call_sign": "[FeedbackRouter]",
            "root": "${ROOT}",
            "intent": "feedback_router.retry",
            "ops": [],
            "verify": [],
        }
        receipt = submit_task(task)
        return {"dispatched": True, "task_id": task_id, "receipt": receipt}
    except Exception as exc:
        logger.warning("feedback_router dispatch failed: %s", exc)
        return {"dispatched": False, "reason": str(exc)}


def _record_block(decision: DecisionRecord) -> dict[str, Any]:
    """Write a block record to activity feed (read path only — no execution)."""
    record = {
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "policy.block",
        "decision_id": decision.decision_id,
        "action": decision.action,
        "source_run_id": decision.source_run_id,
        "classification": decision.classification,
    }
    try:
        import os
        import json
        from pathlib import Path

        runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
        if runtime_root:
            feed = Path(runtime_root) / "logs" / "activity_feed.jsonl"
            feed.parent.mkdir(parents=True, exist_ok=True)
            with feed.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
    except Exception as exc:
        logger.warning("feedback_router block record write failed: %s", exc)
    return {"blocked": True, "record": record}


def route(
    verdict: str,
    decision: DecisionRecord,
) -> dict[str, Any]:
    """Route a policy verdict to the appropriate target.

    Args:
        verdict:  "ALLOW" | "BLOCK" | "ESCALATE"
        decision: The classified DecisionRecord.

    Returns:
        Dict describing routing outcome.
    """
    verdict = verdict.upper().strip()

    if verdict == "ALLOW":
        result = _submit_to_dispatcher(decision)
        return {"routed_to": "dispatcher", "verdict": verdict, **result}

    if verdict == "BLOCK":
        result = _record_block(decision)
        return {"routed_to": "activity_feed", "verdict": verdict, **result}

    # ESCALATE (default for unknown verdicts too)
    try:
        enqueue_operator_case(decision, reason=verdict)
        return {"routed_to": "operator_queue", "verdict": verdict, "queued": True}
    except RuntimeError as exc:
        logger.warning("feedback_router escalate failed: %s", exc)
        return {"routed_to": "operator_queue", "verdict": verdict, "queued": False, "error": str(exc)}
