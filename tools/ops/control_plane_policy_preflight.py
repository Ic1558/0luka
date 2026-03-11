from __future__ import annotations

import math
from typing import Any

from tools.ops.control_plane_policy_change_proposals import PolicyProposalError
from tools.ops.control_plane_policy_versions import read_live_policy


MIN_THRESHOLD = 0.50
MAX_THRESHOLD = 0.95
MAX_DELTA = 0.20
SUPPORTED_COMPONENT = "auto_retry_threshold"


def _coerce_numeric(value: Any) -> float:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError as exc:
            raise PolicyProposalError("invalid_target_value") from exc
    if not isinstance(value, (int, float)):
        raise PolicyProposalError("invalid_target_value")
    numeric = float(value)
    if math.isnan(numeric) or math.isinf(numeric):
        raise PolicyProposalError("invalid_target_value")
    return round(numeric, 2)


def validate_policy_target(
    *,
    policy_component: str,
    target_value: Any,
    current_value: Any,
) -> dict[str, Any]:
    component = str(policy_component or "").strip()
    if component != SUPPORTED_COMPONENT:
        raise PolicyProposalError("invalid_policy_component")
    checks = {
        "type_valid": False,
        "range_valid": False,
        "delta_valid": False,
    }
    try:
        numeric_target = _coerce_numeric(target_value)
    except PolicyProposalError:
        return {
            "policy_component": component,
            "target_value": target_value,
            "is_valid": False,
            "checks": checks,
            "reason": "target_value_not_numeric",
        }
    checks["type_valid"] = True
    checks["range_valid"] = MIN_THRESHOLD <= numeric_target <= MAX_THRESHOLD
    try:
        numeric_current = _coerce_numeric(current_value)
    except PolicyProposalError:
        return {
            "policy_component": component,
            "target_value": numeric_target,
            "is_valid": False,
            "checks": checks,
            "reason": "current_value_unreadable",
        }
    checks["delta_valid"] = abs(numeric_target - numeric_current) <= MAX_DELTA
    if not checks["range_valid"]:
        reason = "target_value_outside_safe_policy_envelope"
    elif not checks["delta_valid"]:
        reason = "target_value_delta_exceeds_safe_step"
    else:
        reason = "ok"
    return {
        "policy_component": component,
        "target_value": numeric_target,
        "is_valid": all(checks.values()),
        "checks": checks,
        "reason": reason,
    }


def load_policy_preflight(
    *,
    runtime_root,
    policy_component: str,
    target_value: Any,
) -> dict[str, Any]:
    live = read_live_policy(runtime_root)
    return validate_policy_target(
        policy_component=policy_component,
        target_value=target_value,
        current_value=live.get("current_value"),
    )
