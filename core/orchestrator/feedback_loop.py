"""AG-18: Minimal bounded feedback loop.

Flow:
  classify → persist → policy_gate → ALLOW: bounded retry dispatch
                                   → BLOCK/ESCALATE: operator queue

Safety constraints:
  - No direct shell execution
  - No git mutation
  - No repo writes outside runtime state
  - Only dispatcher-compatible path for actions
  - max_retry = 1 enforced by policy_gate
"""
from __future__ import annotations

import logging
import time
from typing import Any

from core.decision.models import DecisionRecord
from core.decision import decision_store
from core.operator.operator_queue import enqueue_operator_case
from core.policy.policy_gate import policy_verdict
from tools.ops.decision_engine import classify_once, map_signal_to_action

logger = logging.getLogger(__name__)


def _compute_confidence(
    operator_status: Any,
    runtime_status: Any,
    policy_drift: Any,
) -> float:
    def _ok(v: Any) -> bool | None:
        return v.get("ok") if isinstance(v, dict) and isinstance(v.get("ok"), bool) else None

    def _drift(v: Any) -> int | None:
        dc = v.get("drift_count") if isinstance(v, dict) else None
        return dc if isinstance(dc, int) and not isinstance(dc, bool) else None

    op = _ok(operator_status)
    rt = _ok(runtime_status)
    dc = _drift(policy_drift)
    if op is None or rt is None or dc is None:
        return 0.3
    if op and rt and dc == 0:
        return 0.9
    return 0.6


def _execute_allowed_decision(record: DecisionRecord) -> dict[str, Any]:
    """Bounded action helper — only supports 'retry' via dispatcher submit path."""
    action = record.action.strip().lower()
    if action == "retry":
        return _submit_retry(record.source_run_id)
    # NO_ACTION and other safe terminals — nothing to dispatch
    return {"routed": "no_action", "action": record.action}


def _submit_retry(source_run_id: str) -> dict[str, Any]:
    """Submit a retry sentinel task through the dispatcher path only."""
    try:
        from core.submit import submit_task

        task_id = f"retry_{source_run_id[:20]}_{int(time.time())}"
        task: dict[str, Any] = {
            "task_id": task_id,
            "author": "feedback_loop",
            "schema_version": "clec.v1",
            "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "call_sign": "[FeedbackLoop]",
            "root": "${ROOT}",
            "intent": "feedback_loop.retry",
            "ops": [],
            "verify": [],
        }
        receipt = submit_task(task)
        return {"routed": "dispatcher", "task_id": task_id, "receipt": receipt}
    except Exception as exc:
        logger.warning("retry submit failed: %s", exc)
        return {"routed": "failed", "reason": str(exc)}


def run_loop(
    run_id: str,
    operator_status: Any,
    runtime_status: Any,
    policy_drift: Any,
    *,
    ts_utc: str | None = None,
) -> dict[str, Any]:
    """Run one feedback-loop cycle.

    Args:
        run_id:          Identifier for the run being evaluated.
        operator_status: Dict with at least {"ok": bool}.
        runtime_status:  Dict with at least {"ok": bool}.
        policy_drift:    Dict with at least {"drift_count": int}.
        ts_utc:          Optional override timestamp.

    Returns:
        Dict with decision_id, classification, action, verdict, result.
    """
    if ts_utc is None:
        ts_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Step 1: classify (pure function — no side effects)
    classification = classify_once(operator_status, runtime_status, policy_drift)
    action = map_signal_to_action(
        classification.upper() if isinstance(classification, str) else "UNKNOWN"
    )
    confidence = _compute_confidence(operator_status, runtime_status, policy_drift)

    # Step 2: build decision record (no verdict yet)
    record = DecisionRecord.make(
        source_run_id=run_id,
        classification=classification or "unknown",
        action=action,
        confidence=confidence,
        policy_verdict="PENDING",
        ts_utc=ts_utc,
    )

    # Step 3: persist preliminary record
    try:
        decision_store.append_decision(record)
        decision_store.write_latest(record)
    except RuntimeError as exc:
        logger.warning("decision persist (pre-gate) failed: %s", exc)

    # Step 4: policy gate
    prior = decision_store.list_recent(limit=50)
    verdict = policy_verdict(record, prior_decisions=prior)
    record.policy_verdict = verdict

    # Step 5: update latest with final verdict
    try:
        decision_store.write_latest(record)
    except RuntimeError as exc:
        logger.warning("decision persist (post-gate) failed: %s", exc)

    # Step 6: route
    if verdict == "ALLOW":
        result = _execute_allowed_decision(record)
    else:
        try:
            enqueue_operator_case(record, reason=verdict)
        except RuntimeError as exc:
            logger.warning("operator queue enqueue failed: %s", exc)
        result = {"routed": "operator_queue", "reason": verdict}

    return {
        "decision_id": record.decision_id,
        "classification": record.classification,
        "action": record.action,
        "confidence": record.confidence,
        "verdict": verdict,
        "result": result,
    }
