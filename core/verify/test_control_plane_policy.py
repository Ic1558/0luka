from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.control_plane_policy import (
    POLICY_AUTO_ALLOWED,
    POLICY_HUMAN_APPROVAL_REQUIRED,
    POLICY_MANUAL_ONLY,
    SAFE_LANE_NONE,
    SAFE_LANE_SUPERVISED_ESCALATION,
    SAFE_LANE_SUPERVISED_RETRY,
    derive_policy_verdict,
)
from tools.ops.control_plane_policy_guard import (
    AUTO_LANE_ACTIVE,
    AUTO_LANE_FROZEN,
    apply_auto_lane_guard,
    derive_auto_lane_guard,
)


def test_no_action_suggestion_is_manual_only() -> None:
    payload = derive_policy_verdict(
        {"decision_id": "d1", "trace_id": "t1"},
        {
            "decision_id": "d1",
            "trace_id": "t1",
            "suggestion": "NO_ACTION_RECOMMENDED",
            "confidence_band": "LOW",
            "decision_state": "APPROVED",
            "execution_outcome": "EXECUTION_SUCCEEDED",
        },
        [],
    )

    assert payload["policy_verdict"] == POLICY_MANUAL_ONLY
    assert payload["policy_safe_lane"] == SAFE_LANE_NONE


def test_retry_low_confidence_requires_human_approval() -> None:
    payload = derive_policy_verdict(
        {"decision_id": "d2", "trace_id": "t2"},
        {
            "decision_id": "d2",
            "trace_id": "t2",
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "LOW",
            "decision_state": "APPROVED",
            "execution_outcome": "EXECUTION_FAILED",
        },
        [],
    )

    assert payload["policy_verdict"] == POLICY_HUMAN_APPROVAL_REQUIRED
    assert payload["policy_safe_lane"] == SAFE_LANE_SUPERVISED_RETRY


def test_escalation_low_confidence_requires_human_approval() -> None:
    payload = derive_policy_verdict(
        {"decision_id": "d3", "trace_id": "t3"},
        {
            "decision_id": "d3",
            "trace_id": "t3",
            "suggestion": "ESCALATION_RECOMMENDED",
            "confidence_band": "LOW",
            "decision_state": "APPROVED",
            "execution_outcome": "EXECUTION_UNKNOWN",
        },
        [],
    )

    assert payload["policy_verdict"] == POLICY_HUMAN_APPROVAL_REQUIRED
    assert payload["policy_safe_lane"] == SAFE_LANE_SUPERVISED_ESCALATION


def test_retry_high_confidence_with_prior_alignment_is_auto_allowed() -> None:
    payload = derive_policy_verdict(
        {"decision_id": "d4", "trace_id": "t4"},
        {
            "decision_id": "d4",
            "trace_id": "t4",
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "HIGH",
            "decision_state": "APPROVED",
            "execution_outcome": "EXECUTION_FAILED",
        },
        [
            {"alignment": "MATCHED_SUGGESTION", "operator_action": "RETRY_EXECUTION"},
            {"alignment": "MATCHED_SUGGESTION", "operator_action": "RETRY_EXECUTION"},
        ],
    )

    assert payload["policy_verdict"] == POLICY_AUTO_ALLOWED
    assert payload["policy_safe_lane"] == SAFE_LANE_SUPERVISED_RETRY
    assert payload["alignment_count"] == 2


def test_retry_high_confidence_with_single_alignment_is_not_auto_allowed() -> None:
    payload = derive_policy_verdict(
        {"decision_id": "d4b", "trace_id": "t4b"},
        {
            "decision_id": "d4b",
            "trace_id": "t4b",
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "HIGH",
            "decision_state": "APPROVED",
            "execution_outcome": "EXECUTION_FAILED",
        },
        [{"alignment": "MATCHED_SUGGESTION", "operator_action": "RETRY_EXECUTION"}],
    )

    assert payload["policy_verdict"] == POLICY_HUMAN_APPROVAL_REQUIRED
    assert payload["policy_safe_lane"] == SAFE_LANE_SUPERVISED_RETRY
    assert payload["alignment_count"] == 1


def test_missing_decision_is_manual_only() -> None:
    payload = derive_policy_verdict(
        None,
        {
            "decision_id": None,
            "trace_id": None,
            "suggestion": "NO_ACTION_RECOMMENDED",
            "confidence_band": "LOW",
            "decision_state": None,
            "execution_outcome": None,
        },
        [],
    )

    assert payload["policy_verdict"] == POLICY_MANUAL_ONLY
    assert payload["policy_safe_lane"] == SAFE_LANE_NONE


def test_ambiguous_outcome_is_not_auto_allowed() -> None:
    payload = derive_policy_verdict(
        {"decision_id": "d5", "trace_id": "t5"},
        {
            "decision_id": "d5",
            "trace_id": "t5",
            "suggestion": "ESCALATION_RECOMMENDED",
            "confidence_band": "MEDIUM",
            "decision_state": "APPROVED",
            "execution_outcome": "EXECUTION_UNKNOWN",
        },
        [{"alignment": "MATCHED_SUGGESTION", "operator_action": "ESCALATE_ISSUE"}],
    )

    assert payload["policy_verdict"] != POLICY_AUTO_ALLOWED
    assert payload["policy_safe_lane"] == SAFE_LANE_SUPERVISED_ESCALATION


def test_healthy_stats_keep_auto_lane_active() -> None:
    guard = derive_auto_lane_guard(
        {
            "stats_available": True,
            "auto_retry_triggered": 1,
            "success_rate": 1.0,
            "policy_state": "POLICY_HEALTHY",
            "warning": None,
        }
    )

    assert guard["auto_lane_state"] == AUTO_LANE_ACTIVE


def test_degraded_stats_freeze_auto_lane() -> None:
    guard = derive_auto_lane_guard(
        {
            "stats_available": True,
            "auto_retry_triggered": 2,
            "success_rate": 0.5,
            "policy_state": "POLICY_DEGRADED",
            "warning": "Policy reliability degraded. Review recommended.",
        }
    )

    assert guard["auto_lane_state"] == AUTO_LANE_FROZEN
    assert guard["auto_lane_reason"] == "policy_degraded"


def test_missing_stats_fail_closed_to_frozen() -> None:
    guard = derive_auto_lane_guard({"stats_available": False})

    assert guard["auto_lane_state"] == AUTO_LANE_FROZEN
    assert guard["auto_lane_reason"] == "policy_stats_unavailable"


def test_guard_downgrades_auto_allowed_retry_when_frozen() -> None:
    payload = apply_auto_lane_guard(
        {
            "decision_id": "d6",
            "trace_id": "t6",
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "HIGH",
            "policy_verdict": POLICY_AUTO_ALLOWED,
            "policy_reason": "high_confidence_retry_after_repeated_operator_alignment",
            "policy_safe_lane": SAFE_LANE_SUPERVISED_RETRY,
        },
        {
            "stats_available": True,
            "auto_retry_triggered": 2,
            "success_rate": 0.5,
            "policy_state": "POLICY_DEGRADED",
            "warning": "Policy reliability degraded. Review recommended.",
        },
    )

    assert payload["policy_verdict"] == POLICY_HUMAN_APPROVAL_REQUIRED
    assert payload["policy_verdict_raw"] == POLICY_AUTO_ALLOWED
    assert payload["policy_safe_lane"] == SAFE_LANE_SUPERVISED_RETRY
    assert payload["auto_lane_state"] == AUTO_LANE_FROZEN
