from __future__ import annotations

from typing import Any


AUTO_LANE_ACTIVE = "AUTO_LANE_ACTIVE"
AUTO_LANE_FROZEN = "AUTO_LANE_FROZEN"
AUTO_LANE_FREEZE_EVENT = "POLICY_AUTO_LANE_FROZEN"
AUTO_LANE_UNFREEZE_REQUESTED_EVENT = "POLICY_AUTO_LANE_UNFREEZE_REQUESTED"
AUTO_LANE_UNFROZEN_EVENT = "POLICY_AUTO_LANE_UNFROZEN"


def latest_auto_lane_lifecycle(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    latest: dict[str, Any] | None = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("event") in {
            AUTO_LANE_FREEZE_EVENT,
            AUTO_LANE_UNFREEZE_REQUESTED_EVENT,
            AUTO_LANE_UNFROZEN_EVENT,
        }:
            latest = row
    return latest


def derive_auto_lane_guard(
    stats: dict[str, Any] | None,
    *,
    lifecycle_event: dict[str, Any] | None = None,
) -> dict[str, str | None]:
    if isinstance(lifecycle_event, dict) and lifecycle_event.get("event") == AUTO_LANE_UNFROZEN_EVENT:
        return {
            "auto_lane_state": AUTO_LANE_ACTIVE,
            "auto_lane_reason": "manual_policy_review_completed",
            "auto_lane_lifecycle_event": AUTO_LANE_UNFROZEN_EVENT,
            "auto_lane_operator_note": lifecycle_event.get("operator_note"),
        }

    if not isinstance(stats, dict):
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_stats_unavailable",
            "auto_lane_lifecycle_event": lifecycle_event.get("event") if isinstance(lifecycle_event, dict) else None,
            "auto_lane_operator_note": lifecycle_event.get("operator_note") if isinstance(lifecycle_event, dict) else None,
        }
    if stats.get("stats_available") is False:
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_stats_unavailable",
            "auto_lane_lifecycle_event": lifecycle_event.get("event") if isinstance(lifecycle_event, dict) else None,
            "auto_lane_operator_note": lifecycle_event.get("operator_note") if isinstance(lifecycle_event, dict) else None,
        }
    if int(stats.get("auto_retry_triggered") or 0) == 0:
        return {
            "auto_lane_state": AUTO_LANE_ACTIVE,
            "auto_lane_reason": "no_degradation_evidence",
            "auto_lane_lifecycle_event": lifecycle_event.get("event") if isinstance(lifecycle_event, dict) else None,
            "auto_lane_operator_note": lifecycle_event.get("operator_note") if isinstance(lifecycle_event, dict) else None,
        }
    if str(stats.get("policy_state") or "") == "POLICY_DEGRADED":
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_degraded",
            "auto_lane_lifecycle_event": lifecycle_event.get("event") if isinstance(lifecycle_event, dict) else None,
            "auto_lane_operator_note": lifecycle_event.get("operator_note") if isinstance(lifecycle_event, dict) else None,
        }
    if stats.get("warning"):
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_warning_present",
            "auto_lane_lifecycle_event": lifecycle_event.get("event") if isinstance(lifecycle_event, dict) else None,
            "auto_lane_operator_note": lifecycle_event.get("operator_note") if isinstance(lifecycle_event, dict) else None,
        }
    success_rate = stats.get("success_rate")
    if not isinstance(success_rate, (int, float)):
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_success_rate_unavailable",
            "auto_lane_lifecycle_event": lifecycle_event.get("event") if isinstance(lifecycle_event, dict) else None,
            "auto_lane_operator_note": lifecycle_event.get("operator_note") if isinstance(lifecycle_event, dict) else None,
        }
    if float(success_rate) < 0.70:
        return {
            "auto_lane_state": AUTO_LANE_FROZEN,
            "auto_lane_reason": "policy_success_rate_below_threshold",
            "auto_lane_lifecycle_event": lifecycle_event.get("event") if isinstance(lifecycle_event, dict) else None,
            "auto_lane_operator_note": lifecycle_event.get("operator_note") if isinstance(lifecycle_event, dict) else None,
        }
    return {
        "auto_lane_state": AUTO_LANE_ACTIVE,
        "auto_lane_reason": "policy_within_threshold",
        "auto_lane_lifecycle_event": lifecycle_event.get("event") if isinstance(lifecycle_event, dict) else None,
        "auto_lane_operator_note": lifecycle_event.get("operator_note") if isinstance(lifecycle_event, dict) else None,
    }


def apply_auto_lane_guard(policy_payload: dict[str, Any], stats: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(policy_payload)
    guard = derive_auto_lane_guard(stats)
    payload["auto_lane_state"] = guard["auto_lane_state"]
    payload["auto_lane_reason"] = guard["auto_lane_reason"]
    payload["auto_lane_lifecycle_event"] = guard.get("auto_lane_lifecycle_event")
    payload["auto_lane_operator_note"] = guard.get("auto_lane_operator_note")

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
