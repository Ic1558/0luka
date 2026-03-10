from __future__ import annotations

from typing import Any


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _status_value(payload: dict[str, Any]) -> str | None:
    for key in ("overall_status", "status"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def _health_ok(payload: dict[str, Any]) -> bool | None:
    if isinstance(payload.get("ok"), bool):
        return payload["ok"]

    status = _status_value(payload)
    if status is None:
        return None
    return status in {"OK", "HEALTHY"}


def _drift_detected(payload: dict[str, Any]) -> bool | None:
    if isinstance(payload.get("ok"), bool):
        return not payload["ok"]

    drift_count = payload.get("drift_count")
    if isinstance(drift_count, int):
        return drift_count > 0

    return None


def classify_once(
    operator_status: Any,
    runtime_status: Any,
    policy_drift: Any,
    ts_utc: Any,
) -> dict[str, Any] | None:
    operator = _as_dict(operator_status)
    runtime = _as_dict(runtime_status)
    drift = _as_dict(policy_drift)
    if operator is None or runtime is None or drift is None:
        return None
    if not isinstance(ts_utc, str) or not ts_utc.strip():
        return None

    operator_ok = _health_ok(operator)
    runtime_ok = _health_ok(runtime)
    drift_active = _drift_detected(drift)
    if operator_ok is None or runtime_ok is None or drift_active is None:
        return None

    if drift_active:
        return {
            "ts_utc": ts_utc,
            "type": "drift_detected",
            "source": ["policy_drift"],
            "evidence": {
                "policy_drift": {
                    "ok": drift.get("ok"),
                    "drift_count": drift.get("drift_count"),
                }
            },
        }

    if operator_ok and runtime_ok:
        return {
            "ts_utc": ts_utc,
            "type": "nominal",
            "source": ["operator_status", "runtime_status", "policy_drift"],
            "evidence": {
                "operator_status": {
                    "ok": operator.get("ok"),
                    "overall_status": operator.get("overall_status"),
                },
                "runtime_status": {
                    "ok": runtime.get("ok"),
                    "overall_status": runtime.get("overall_status"),
                },
                "policy_drift": {
                    "ok": drift.get("ok"),
                    "drift_count": drift.get("drift_count"),
                },
            },
        }

    return None
