"""Operator-facing status surface for qs application jobs."""

from __future__ import annotations

from enum import Enum

from qs.app.jobs import JobContract, JobState


class ActionBoundary(str, Enum):
    SAFE_READ_ONLY = "safe_read_only"
    APPROVAL_REQUIRED = "approval_required"
    PUBLISH_FINALIZE = "publish_finalize"


def classify_action_boundary(contract: JobContract, action: str) -> ActionBoundary:
    """Classify actions to enforce explicit approval-aware boundaries in qs."""

    publish_actions = {"publish", "finalize", "commit"}
    if action in publish_actions:
        return ActionBoundary.PUBLISH_FINALIZE
    if contract.requires_approval:
        return ActionBoundary.APPROVAL_REQUIRED
    return ActionBoundary.SAFE_READ_ONLY


def emit_status(
    contract: JobContract,
    state: JobState,
    action: str,
    detail: str,
) -> dict[str, object]:
    """Return deterministic status payload consumable by Mission Control surfaces."""

    return {
        "job_type": contract.job_type,
        "project_id": contract.project_id,
        "state": state.value,
        "requires_approval": contract.requires_approval,
        "action": action,
        "action_boundary": classify_action_boundary(contract, action).value,
        "detail": detail,
    }
