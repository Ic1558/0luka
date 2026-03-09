"""Approval boundary rules for Phase A application-layer jobs."""

from __future__ import annotations

APPROVAL_RULES: dict[str, bool] = {
    "boq_generate": False,
    "compliance_check": False,
    "po_generate": True,
}


def requires_approval(job_type: str) -> bool:
    """Return whether a job requires approval; fail closed for unknown jobs."""

    if job_type not in APPROVAL_RULES:
        raise ValueError(f"Unknown job type: {job_type}")
    return APPROVAL_RULES[job_type]
