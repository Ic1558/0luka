"""Deterministic job contracts for the qs application layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class JobState(str, Enum):
    """Allowed execution states for qs jobs."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class JobContract:
    """Schema-like contract used for deterministic job registration."""

    job_type: str
    project_id: str
    inputs: dict[str, str]
    requires_approval: bool
    expected_outputs: dict[str, str]
    allowed_states: tuple[JobState, ...]


DEFAULT_ALLOWED_STATES = (
    JobState.QUEUED,
    JobState.RUNNING,
    JobState.WAITING_APPROVAL,
    JobState.SUCCEEDED,
    JobState.FAILED,
)


JOB_DEFINITIONS: dict[str, dict[str, Any]] = {
    "boq_generate": {
        "inputs": {
            "drawing_ref": "str",
            "measurement_profile": "str",
        },
        "expected_outputs": {
            "boq_id": "str",
            "line_items": "list[dict[str, Any]]",
        },
        "requires_approval": False,
    },
    "compliance_check": {
        "inputs": {
            "boq_id": "str",
            "code_set": "str",
        },
        "expected_outputs": {
            "compliance_report_id": "str",
            "violations": "list[dict[str, Any]]",
        },
        "requires_approval": False,
    },
    "po_generate": {
        "inputs": {
            "boq_id": "str",
            "vendor_profile": "str",
        },
        "expected_outputs": {
            "po_id": "str",
            "po_document_uri": "str",
        },
        "requires_approval": True,
    },
}


def get_job_contract(job_type: str, project_id: str) -> JobContract:
    """Return a deterministic contract object for a supported job type."""

    if job_type not in JOB_DEFINITIONS:
        raise ValueError(f"Unsupported job type: {job_type}")

    definition = JOB_DEFINITIONS[job_type]
    return JobContract(
        job_type=job_type,
        project_id=project_id,
        inputs=definition["inputs"],
        requires_approval=definition["requires_approval"],
        expected_outputs=definition["expected_outputs"],
        allowed_states=DEFAULT_ALLOWED_STATES,
    )
