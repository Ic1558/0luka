from __future__ import annotations

from typing import Any


AUTO_LANE_ACTIVE = "AUTO_LANE_ACTIVE"
AUTO_LANE_FROZEN = "AUTO_LANE_FROZEN"


def derive_auto_lane_guard(stats: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(stats, dict):
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_stats_unavailable",
        }
    if stats.get("stats_available") is False:
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_stats_unavailable",
        }
    if int(stats.get("auto_retry_triggered") or 0) == 0:
        return {
            "auto_lane_state": AUTO_LANE_ACTIVE,
            "auto_lane_reason": "no_degradation_evidence",
        }
    if str(stats.get("policy_state") or "") == "POLICY_DEGRADED":
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_degraded",
        }
    if stats.get("warning"):
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_warning_present",
        }
    success_rate = stats.get("success_rate")
    if not isinstance(success_rate, (int, float)):
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_success_rate_unavailable",
        }
    if float(success_rate) < 0.70:
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_success_rate_below_threshold",
        }
    return {
        "auto_lane_state": AUTO_LANE_ACTIVE,
        "auto_lane_reason": "policy_within_threshold",
    }


def apply_auto_lane_guard(policy_payload: dict[str, Any], stats: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(policy_payload)
    guard = derive_auto_lane_guard(stats)
    payload["auto_lane_state"] = guard["auto_lane_state"]
    payload["auto_lane_reason"] = guard["auto_lane_reason"]

    if (
        payload.get("policy_verdict") == "AUTO_ALLOWED"
        and payload.get("policy_safe_lane") == "SUPERVISED_RETRY"
        and payload["auto_lane_state"] == AUTO_LANE_FROZEN
    ):
        payload["policy_verdict_raw"] = payload.get("policy_verdict")
        payload["policy_safe_lane_raw"] = payload.get("policy_safe_lane")
        payload["policy_verdict"] = "HUMAN_APPROVAL_REQUIRED"
        payload["policy_reason"] = f"auto_lane_frozen_due_to_{guard['auto_lane_reason']}"
    return payload
