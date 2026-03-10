from __future__ import annotations

from typing import Any


def _read_ok(payload: Any) -> bool | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("ok")
    return value if isinstance(value, bool) else None


def _read_drift_count(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("drift_count")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def classify_once(
    operator_status: Any,
    runtime_status: Any,
    policy_drift: Any,
) -> str | None:
    operator_ok = _read_ok(operator_status)
    runtime_ok = _read_ok(runtime_status)
    drift_count = _read_drift_count(policy_drift)

    if operator_ok is None or runtime_ok is None or drift_count is None:
        return None
    if operator_ok is False:
        return "drift_detected"
    if runtime_ok is False:
        return "drift_detected"
    if drift_count > 0:
        return "drift_detected"
    return "nominal"
