from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.control_plane_policy_tuning_simulator import derive_tuning_preview


def _candidate_context(
    decision_id: str,
    *,
    confidence_band: str = "HIGH",
    alignment_count: int = 2,
    execution_outcome: str = "EXECUTION_FAILED",
) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "trace_id": f"trace-{decision_id}",
        "latest_decision": {
            "decision_id": decision_id,
            "trace_id": f"trace-{decision_id}",
            "operator_status": "APPROVED",
            "execution": {"outcome_status": execution_outcome},
        },
        "policy_payload": {
            "suggestion": "RETRY_RECOMMENDED",
            "policy_verdict": "AUTO_ALLOWED" if confidence_band == "HIGH" and alignment_count >= 2 else "HUMAN_APPROVAL_REQUIRED",
            "policy_safe_lane": "SUPERVISED_RETRY",
            "confidence_band": confidence_band,
            "alignment_count": alignment_count,
            "auto_lane_state": "AUTO_LANE_ACTIVE",
        },
    }


def test_simulator_baseline_matches_current_live_assumptions() -> None:
    candidate_contexts = [
        _candidate_context("d1", confidence_band="HIGH", alignment_count=2),
        _candidate_context("d2", confidence_band="HIGH", alignment_count=1),
        _candidate_context("d3", confidence_band="LOW", alignment_count=2),
        _candidate_context("d4", confidence_band="HIGH", alignment_count=3),
    ]

    payload = derive_tuning_preview(
        candidate_contexts,
        alignment_threshold=2,
        confidence_requirement="HIGH",
        recent_cases=4,
        auto_lane_state="AUTO_LANE_ACTIVE",
    )

    assert payload["baseline"]["alignment_threshold"] == 2
    assert payload["baseline"]["confidence_requirement"] == "HIGH"
    assert payload["baseline"]["eligible_count"] == 2
    assert payload["baseline"]["blocked_count"] == 2
    assert payload["baseline"]["eligible_ratio"] == 0.5


def test_alignment_threshold_simulation_changes_counts_and_blocker_shift_deterministically() -> None:
    candidate_contexts = [
        _candidate_context("d1", confidence_band="HIGH", alignment_count=2),
        _candidate_context("d2", confidence_band="HIGH", alignment_count=1),
        _candidate_context("d3", confidence_band="HIGH", alignment_count=1),
        _candidate_context("d4", confidence_band="LOW", alignment_count=2),
    ]

    payload = derive_tuning_preview(
        candidate_contexts,
        alignment_threshold=1,
        confidence_requirement="HIGH",
        recent_cases=4,
        auto_lane_state="AUTO_LANE_ACTIVE",
    )

    assert payload["simulation"]["alignment_threshold"] == 1
    assert payload["simulation"]["eligible_count"] == 3
    assert payload["simulation"]["blocked_count"] == 1
    assert payload["difference"]["eligible_delta"] == 2
    assert payload["difference"]["blocked_delta"] == -2
    assert payload["difference"]["eligible_ratio_delta"] == 0.5
    assert payload["blocker_shift"][0]["reason"] == "trust_alignment_count_below_threshold"
    assert payload["blocker_shift"][0]["baseline_count"] == 2
    assert payload["blocker_shift"][0]["simulated_count"] == 0
    assert "simulation reduced trust-alignment blocking" in payload["notes"]


def test_simulator_recomputes_readiness_band_under_simulated_conditions() -> None:
    candidate_contexts = [
        _candidate_context("d1", confidence_band="HIGH", alignment_count=1),
        _candidate_context("d2", confidence_band="HIGH", alignment_count=1),
        _candidate_context("d3", confidence_band="HIGH", alignment_count=2),
        _candidate_context("d4", confidence_band="MEDIUM", alignment_count=2),
    ]

    payload = derive_tuning_preview(
        candidate_contexts,
        alignment_threshold=1,
        confidence_requirement="MEDIUM",
        recent_cases=4,
        auto_lane_state="AUTO_LANE_ACTIVE",
    )

    assert payload["baseline"]["readiness_band"] == "NOT_READY"
    assert payload["simulation"]["readiness_band"] == "READY"


def test_simulator_handles_sparse_data_safely() -> None:
    payload = derive_tuning_preview(
        [],
        alignment_threshold=1,
        confidence_requirement="MEDIUM",
        recent_cases=20,
        auto_lane_state="AUTO_LANE_ACTIVE",
    )

    assert payload["window"]["cases_observed"] == 0
    assert payload["baseline"]["eligible_count"] == 0
    assert payload["simulation"]["eligible_count"] == 0
    assert payload["blocker_shift"] == []
    assert payload["notes"] == ["insufficient evidence for sandbox tuning preview"]
    assert payload["stats_available"] is False
