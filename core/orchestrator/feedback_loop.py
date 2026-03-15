"""AG-18/AG-19: Bounded feedback loop — classify → plan → gate → execute → verify.

AG-18 flow: classify → persist → policy_gate(decision) → route
AG-19 flow: classify → persist → policy_gate(decision) → planner → plan_store
            → policy_gate(plan) → executor → verifier → persist results

Safety:
  - No direct shell execution
  - No git mutation
  - No repo writes outside $LUKA_RUNTIME_ROOT
  - All actions through dispatcher-compatible path
  - max_retry = 1 enforced at decision + plan level
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from core.decision.models import DecisionRecord
from core.decision import decision_store
from core.executor.executor import execute_plan
from core.operator.operator_queue import enqueue_operator_case
from core.planner.planner import create_plan
from core.planner import plan_store
from core.policy.policy_gate import plan_allowed, policy_verdict
from core.verifier.verifier import verify_execution
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

    # Step 5b: AG-24A safety gate — emergency stop blocks action path
    try:
        from core.safety.emergency_stop import is_emergency_stop_active
        if is_emergency_stop_active():
            logger.warning("feedback_loop halted: emergency_stop active (run=%s)", run_id)
            return {
                "decision_id": record.decision_id,
                "classification": record.classification,
                "action": record.action,
                "confidence": record.confidence,
                "verdict": verdict,
                "result": {"routed": "emergency_stop", "reason": "emergency_stop_active"},
            }
    except Exception as exc:
        logger.warning("emergency_stop check failed (fail-open): %s", exc)

    # Step 6: route via AG-19 planner → executor → verifier
    if verdict != "ALLOW":
        try:
            enqueue_operator_case(record, reason=verdict)
        except RuntimeError as exc:
            logger.warning("operator queue enqueue failed: %s", exc)
        return {
            "decision_id": record.decision_id,
            "classification": record.classification,
            "action": record.action,
            "confidence": record.confidence,
            "verdict": verdict,
            "result": {"routed": "operator_queue", "reason": verdict},
        }

    # AG-19: plan
    plan = create_plan(record, run_state={"run_id": run_id})
    try:
        plan_store.append_plan(plan)
        plan_store.write_latest(plan)
    except RuntimeError as exc:
        logger.warning("plan persist failed: %s", exc)

    # AG-19: plan-level policy gate
    prior_plans = plan_store.list_recent(limit=50)
    plan_verdict = plan_allowed(plan, prior_plans=prior_plans)

    if plan_verdict != "ALLOW":
        try:
            enqueue_operator_case(record, reason=f"plan_{plan_verdict}")
        except RuntimeError as exc:
            logger.warning("plan escalation enqueue failed: %s", exc)
        return {
            "decision_id": record.decision_id,
            "classification": record.classification,
            "action": record.action,
            "confidence": record.confidence,
            "verdict": verdict,
            "plan_verdict": plan_verdict,
            "result": {"routed": "operator_queue", "reason": f"plan_{plan_verdict}"},
        }

    # AG-24/AG-26: runtime safety gate before execution
    try:
        from core.safety.runtime_safety_gate import evaluate_runtime_safety
        safety_verdict = evaluate_runtime_safety({
            "run_id": run_id,
            "action_type": record.action.lower(),
            "policy_verdict": verdict,
            "topology_mode": "STABLE",
            "process_conflict": False,
            "failure_count": 0,
        })
        if safety_verdict != "ALLOW":
            logger.warning("safety gate %s before execute (run=%s)", safety_verdict, run_id)
            try:
                enqueue_operator_case(record, reason=f"safety_{safety_verdict.lower()}")
            except RuntimeError as exc:
                logger.warning("safety escalation enqueue failed: %s", exc)
            return {
                "decision_id": record.decision_id,
                "classification": record.classification,
                "action": record.action,
                "confidence": record.confidence,
                "verdict": verdict,
                "plan_verdict": plan_verdict,
                "result": {"routed": "safety_gate", "reason": safety_verdict},
            }
    except ImportError:
        pass  # AG-24 not available — proceed without safety gate

    # AG-19: execute
    execution_result = execute_plan(plan)
    _persist_execution(execution_result)

    # AG-19: verify
    verification_result = verify_execution(run_id, execution_result)
    _persist_verification(verification_result)

    # escalate if verification failed
    if verification_result.get("status") in ("FAILED", "PARTIAL"):
        try:
            enqueue_operator_case(
                record,
                reason=f"verification_{verification_result['status'].lower()}",
            )
        except RuntimeError as exc:
            logger.warning("verification escalation enqueue failed: %s", exc)

    return {
        "decision_id": record.decision_id,
        "classification": record.classification,
        "action": record.action,
        "confidence": record.confidence,
        "verdict": verdict,
        "plan_id": plan.get("plan_id"),
        "plan_verdict": plan_verdict,
        "execution_id": execution_result.get("execution_id"),
        "execution_status": execution_result.get("status"),
        "verification_id": verification_result.get("verification_id"),
        "verification_status": verification_result.get("status"),
    }


def _persist_execution(execution_result: dict[str, Any]) -> None:
    """Write execution result to execution_log.jsonl and execution_latest.json."""
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        return
    state_dir = Path(runtime_root) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        log = state_dir / "execution_log.jsonl"
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(execution_result, sort_keys=True) + "\n")
        latest = state_dir / "execution_latest.json"
        tmp = state_dir / "execution_latest.json.tmp"
        tmp.write_text(json.dumps(execution_result, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, latest)
    except OSError as exc:
        logger.warning("execution persist failed: %s", exc)


def _persist_verification(verification_result: dict[str, Any]) -> None:
    """Write verification result to verification_log.jsonl and verification_latest.json."""
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        return
    state_dir = Path(runtime_root) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        log = state_dir / "verification_log.jsonl"
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(verification_result, sort_keys=True) + "\n")
        latest = state_dir / "verification_latest.json"
        tmp = state_dir / "verification_latest.json.tmp"
        tmp.write_text(json.dumps(verification_result, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, latest)
    except OSError as exc:
        logger.warning("verification persist failed: %s", exc)
