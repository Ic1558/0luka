"""Deterministic Phase A job contracts for the qs application layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


ALLOWED_STATES: tuple[str, ...] = ("queued", "running", "success", "failed", "blocked")


@dataclass(frozen=True)
class JobContract:
    """Deterministic contract for a supported qs job type."""

    job_type: str
    project_id: str
    inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    requires_approval: bool
    allowed_states: tuple[str, ...] = ALLOWED_STATES


JOB_CONTRACTS: Mapping[str, JobContract] = {
    "boq_generate": JobContract(
        job_type="boq_generate",
        project_id="<project_id>",
        inputs=("model_id", "takeoff_ruleset"),
        expected_outputs=("boq_document", "boq_summary"),
        requires_approval=False,
    ),
    "compliance_check": JobContract(
        job_type="compliance_check",
        project_id="<project_id>",
        inputs=("model_id", "code_pack"),
        expected_outputs=("compliance_report",),
        requires_approval=False,
    ),
    "po_generate": JobContract(
        job_type="po_generate",
        project_id="<project_id>",
        inputs=("vendor_id", "line_items", "currency"),
        expected_outputs=("purchase_order", "approval_trace"),
        requires_approval=True,
    ),
}


def get_job_contract(job_type: str) -> JobContract:
    """Return the contract for a known job type; fail closed for unknown types."""

    contract = JOB_CONTRACTS.get(job_type)
    if contract is None:
        raise ValueError(f"Unsupported job type: {job_type}")
    return contract


def supported_jobs() -> Sequence[str]:
    """Return deterministic job ordering for status emission."""

    return tuple(sorted(JOB_CONTRACTS.keys()))
