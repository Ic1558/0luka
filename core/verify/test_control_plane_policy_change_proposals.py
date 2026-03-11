from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.control_plane_policy_change_proposals import (
    POLICY_COMPONENTS,
    create_policy_change_proposal,
    get_policy_change_proposal,
    list_policy_change_proposals,
)


def test_policy_change_proposal_creation_and_append_only_listing(tmp_path) -> None:
    observability_root = tmp_path / "observability"

    first = create_policy_change_proposal(
        observability_root,
        created_at="2026-03-11T22:00:00Z",
        policy_component="auto_retry_threshold",
        proposed_value=0.80,
        evidence_summary="policy review recommended due to degraded auto-retry reliability",
        simulation_reference="/api/policy/tuning-preview?success_threshold=0.80",
        operator_note="raise retry threshold after review",
    )
    second = create_policy_change_proposal(
        observability_root,
        created_at="2026-03-11T22:05:00Z",
        policy_component="auto_retry_threshold",
        proposed_value=0.85,
        evidence_summary="sandbox tuning preview reduced retry volume",
        simulation_reference="/api/policy/tuning-preview?success_threshold=0.85",
        operator_note=None,
    )

    rows = list_policy_change_proposals(observability_root, limit=10)

    assert len(rows) == 2
    assert rows[0]["proposal_id"] == first["proposal_id"]
    assert rows[1]["proposal_id"] == second["proposal_id"]
    assert rows[0]["status"] == "PROPOSED"
    assert rows[1]["status"] == "PROPOSED"
    assert rows[0]["current_value"] == POLICY_COMPONENTS["auto_retry_threshold"]
    assert rows[1]["current_value"] == POLICY_COMPONENTS["auto_retry_threshold"]


def test_policy_change_proposal_detail_lookup_and_runtime_policy_unchanged(tmp_path) -> None:
    observability_root = tmp_path / "observability"
    record = create_policy_change_proposal(
        observability_root,
        created_at="2026-03-11T22:10:00Z",
        policy_component="auto_retry_threshold",
        proposed_value=0.80,
        evidence_summary="review and simulation support threshold change",
        simulation_reference="/api/policy/tuning-preview?success_threshold=0.80",
        operator_note="capture proposal only",
    )

    found = get_policy_change_proposal(observability_root, record["proposal_id"])

    assert found is not None
    assert found["proposal_id"] == record["proposal_id"]
    assert found["status"] == "PROPOSED"
    assert found["current_value"] == 0.70
    assert POLICY_COMPONENTS["auto_retry_threshold"] == 0.70
