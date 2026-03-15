"""AG-24B: Runtime safety gate — central guard before every live control plane action.

Every action in the live control plane must pass through evaluate_runtime_safety()
before executing. No exceptions.

Returns: ALLOW | BLOCK | ESCALATE | STOP
"""
from __future__ import annotations

import logging
from typing import Any

from core.safety.autonomy_budget import budget_exhausted
from core.safety.emergency_stop import is_emergency_stop_active

logger = logging.getLogger(__name__)

# Repeated-failure threshold: if failure_count >= this, escalate
_FAILURE_ESCALATE_THRESHOLD: int = 3


def evaluate_runtime_safety(context: dict[str, Any]) -> str:
    """Evaluate whether a runtime action is safe to proceed.

    Args:
        context: Dict with keys:
          run_id           (str)  — current run identifier
          action_type      (str)  — type of action (retry, fallback, etc.)
          policy_verdict   (str)  — ALLOW | BLOCK | ESCALATE from policy gate
          topology_mode    (str)  — STABLE | DRAINING | TRANSITIONING | LOCKDOWN
          process_conflict (bool) — whether concurrency conflict detected
          failure_count    (int)  — consecutive failures this run
          emergency_stop   (bool) — override; if omitted, checked from state file
          protected_zone   (bool) — whether target path is in protected zone

    Returns:
        "ALLOW" | "BLOCK" | "ESCALATE" | "STOP"
    """
    run_id = str(context.get("run_id") or "")
    action_type = str(context.get("action_type") or "")
    policy_verdict = str(context.get("policy_verdict") or "ALLOW").upper()
    topology_mode = str(context.get("topology_mode") or "STABLE").upper()
    process_conflict = bool(context.get("process_conflict", False))
    failure_count = int(context.get("failure_count") or 0)
    emergency_stop = context.get("emergency_stop")
    protected_zone = bool(context.get("protected_zone", False))

    # 1. Emergency stop — highest priority
    stop_active = emergency_stop if isinstance(emergency_stop, bool) else is_emergency_stop_active()
    if stop_active:
        logger.warning("safety_gate STOP: emergency stop active (run=%s)", run_id)
        return "STOP"

    # 2. Upstream policy already blocked
    if policy_verdict == "BLOCK":
        logger.info("safety_gate BLOCK: upstream policy verdict=BLOCK (run=%s)", run_id)
        return "BLOCK"

    # 3. Protected zone access
    if protected_zone:
        logger.warning("safety_gate BLOCK: protected zone access attempted (run=%s action=%s)", run_id, action_type)
        return "BLOCK"

    # 4. Topology not stable — block topology-sensitive actions
    _TOPOLOGY_SENSITIVE = frozenset({"policy_rollout", "rollout", "deploy", "topology_change"})
    if topology_mode != "STABLE" and action_type.lower() in _TOPOLOGY_SENSITIVE:
        logger.warning("safety_gate BLOCK: topology=%s action=%s (run=%s)", topology_mode, action_type, run_id)
        return "BLOCK"

    if topology_mode == "LOCKDOWN":
        logger.warning("safety_gate STOP: topology=LOCKDOWN (run=%s)", run_id)
        return "STOP"

    # 5. Process concurrency conflict
    if process_conflict:
        logger.warning("safety_gate ESCALATE: process conflict detected (run=%s)", run_id)
        return "ESCALATE"

    # 6. Repeated failure pattern
    if failure_count >= _FAILURE_ESCALATE_THRESHOLD:
        logger.warning("safety_gate ESCALATE: repeated failures=%d (run=%s)", failure_count, run_id)
        return "ESCALATE"

    # 7. Autonomy budget
    if run_id and budget_exhausted(run_id):
        logger.warning("safety_gate BLOCK: autonomy budget exhausted (run=%s action=%s)", run_id, action_type)
        return "BLOCK"

    # 8. Upstream policy escalate → propagate
    if policy_verdict == "ESCALATE":
        return "ESCALATE"

    return "ALLOW"
