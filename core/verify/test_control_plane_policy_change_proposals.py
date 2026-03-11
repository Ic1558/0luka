from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.control_plane_policy_change_proposals import (
    POLICY_COMPONENTS,
    append_policy_deployment_event,
    approve_policy_change_proposal,
    create_policy_change_proposal,
    get_policy_change_proposal,
    list_policy_change_proposals,
    reject_policy_change_proposal,
)
from tools.ops.control_plane_policy_versions import deploy_policy_version, read_live_policy
from tools.ops.control_plane_policy_versions import get_policy_version, list_policy_versions, rollback_policy_version


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


def test_policy_change_proposal_can_transition_to_approved_and_rejected_append_only(tmp_path) -> None:
    observability_root = tmp_path / "observability"
    approved = create_policy_change_proposal(
        observability_root,
        created_at="2026-03-11T22:20:00Z",
        policy_component="auto_retry_threshold",
        proposed_value=0.80,
        evidence_summary="review supports threshold increase",
        simulation_reference="/api/policy/tuning-preview?success_threshold=0.80",
    )
    rejected = create_policy_change_proposal(
        observability_root,
        created_at="2026-03-11T22:21:00Z",
        policy_component="auto_retry_threshold",
        proposed_value=0.85,
        evidence_summary="higher threshold needs more evidence",
        simulation_reference="/api/policy/tuning-preview?success_threshold=0.85",
    )

    approved_row = approve_policy_change_proposal(
        observability_root,
        proposal_id=approved["proposal_id"],
        created_at="2026-03-11T22:22:00Z",
        operator_note="approved for bounded deployment review",
    )
    rejected_row = reject_policy_change_proposal(
        observability_root,
        proposal_id=rejected["proposal_id"],
        created_at="2026-03-11T22:23:00Z",
        operator_note="reject until more evidence exists",
    )

    rows = list_policy_change_proposals(observability_root, limit=10)

    assert approved_row["status"] == "APPROVED_FOR_IMPLEMENTATION"
    assert rejected_row["status"] == "REJECTED"
    assert rows[0]["status"] == "APPROVED_FOR_IMPLEMENTATION"
    assert rows[1]["status"] == "REJECTED"


def test_policy_change_proposal_deployment_records_version_without_mutating_policy_logic(tmp_path) -> None:
    observability_root = tmp_path / "observability"
    runtime_root = tmp_path / "runtime"
    proposal = create_policy_change_proposal(
        observability_root,
        created_at="2026-03-11T22:30:00Z",
        policy_component="auto_retry_threshold",
        proposed_value=0.80,
        evidence_summary="simulation shows improved expected success rate",
        simulation_reference="/api/policy/tuning-preview?success_threshold=0.80",
    )
    approve_policy_change_proposal(
        observability_root,
        proposal_id=proposal["proposal_id"],
        created_at="2026-03-11T22:31:00Z",
    )
    append_policy_deployment_event(
        observability_root,
        proposal_id=proposal["proposal_id"],
        event="POLICY_DEPLOYMENT_REQUESTED",
        created_at="2026-03-11T22:32:00Z",
        operator_note="deploy approved threshold",
    )

    version = deploy_policy_version(
        runtime_root,
        observability_root,
        proposal_id=proposal["proposal_id"],
        deployed_at="2026-03-11T22:32:00Z",
        policy_component="auto_retry_threshold",
        new_value=0.80,
    )
    append_policy_deployment_event(
        observability_root,
        proposal_id=proposal["proposal_id"],
        event="POLICY_DEPLOYED",
        created_at="2026-03-11T22:32:00Z",
        operator_note="deployment recorded",
    )

    live = read_live_policy(runtime_root)

    assert version["policy_component"] == "auto_retry_threshold"
    assert version["previous_value"] == 0.70
    assert version["new_value"] == 0.80
    assert version["status"] == "ACTIVE"
    assert live["current_value"] == 0.80
    assert live["policy_version_id"] == version["policy_version_id"]
    assert POLICY_COMPONENTS["auto_retry_threshold"] == 0.70


def test_policy_version_history_and_explicit_rollback_are_append_only(tmp_path) -> None:
    observability_root = tmp_path / "observability"
    runtime_root = tmp_path / "runtime"
    proposal = create_policy_change_proposal(
        observability_root,
        created_at="2026-03-11T22:40:00Z",
        policy_component="auto_retry_threshold",
        proposed_value=0.80,
        evidence_summary="raise threshold after controlled review",
        simulation_reference="/api/policy/tuning-preview?success_threshold=0.80",
    )
    approve_policy_change_proposal(
        observability_root,
        proposal_id=proposal["proposal_id"],
        created_at="2026-03-11T22:41:00Z",
    )
    append_policy_deployment_event(
        observability_root,
        proposal_id=proposal["proposal_id"],
        event="POLICY_DEPLOYMENT_REQUESTED",
        created_at="2026-03-11T22:42:00Z",
    )
    deployed = deploy_policy_version(
        runtime_root,
        observability_root,
        proposal_id=proposal["proposal_id"],
        deployed_at="2026-03-11T22:42:00Z",
        policy_component="auto_retry_threshold",
        new_value=0.80,
    )
    append_policy_deployment_event(
        observability_root,
        proposal_id=proposal["proposal_id"],
        event="POLICY_DEPLOYED",
        created_at="2026-03-11T22:42:00Z",
    )

    second = deploy_policy_version(
        runtime_root,
        observability_root,
        proposal_id="proposal_followup",
        deployed_at="2026-03-11T22:42:30Z",
        policy_component="auto_retry_threshold",
        new_value=0.85,
    )

    rolled_back = rollback_policy_version(
        runtime_root,
        observability_root,
        target_version_id=deployed["policy_version_id"],
        rolled_back_at="2026-03-11T22:43:00Z",
        operator_note="restore prior threshold",
    )

    live = read_live_policy(runtime_root)
    versions = list_policy_versions(observability_root, limit=10)
    rollback_record = get_policy_version(observability_root, rolled_back["new_active_version_id"])

    assert live["current_value"] == 0.80
    assert live["policy_version_id"] == rolled_back["new_active_version_id"]
    assert len(versions) == 3
    assert rollback_record is not None
    assert rollback_record["rollback_of_version_id"] == deployed["policy_version_id"]
    assert rollback_record["proposal_id"] is None
    assert rolled_back["rolled_back_from_version_id"] == second["policy_version_id"]


def test_policy_rollback_restores_previous_value_via_new_active_version(tmp_path) -> None:
    observability_root = tmp_path / "observability"
    runtime_root = tmp_path / "runtime"
    first = deploy_policy_version(
        runtime_root,
        observability_root,
        proposal_id="proposal_a",
        deployed_at="2026-03-11T22:50:00Z",
        policy_component="auto_retry_threshold",
        new_value=0.80,
    )
    second = deploy_policy_version(
        runtime_root,
        observability_root,
        proposal_id="proposal_b",
        deployed_at="2026-03-11T22:51:00Z",
        policy_component="auto_retry_threshold",
        new_value=0.85,
    )

    rolled_back = rollback_policy_version(
        runtime_root,
        observability_root,
        target_version_id=first["policy_version_id"],
        rolled_back_at="2026-03-11T22:52:00Z",
    )
    live = read_live_policy(runtime_root)

    assert rolled_back["rolled_back_from_version_id"] == second["policy_version_id"]
    assert rolled_back["rollback_target_version_id"] == first["policy_version_id"]
    assert rolled_back["current_value"] == 0.80
    assert live["current_value"] == 0.80
