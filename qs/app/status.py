"""Deterministic status surface for qs Phase A."""

from __future__ import annotations

from qs.app.jobs import supported_jobs
from qs.app.policy import APPROVAL_RULES


def build_status_payload() -> dict[str, object]:
    """Build a deterministic service status payload."""

    jobs = tuple(supported_jobs())
    approval_jobs = tuple(sorted(job for job, required in APPROVAL_RULES.items() if required))
    return {
        "service": "qs",
        "jobs_supported": list(jobs),
        "approval_required_jobs": list(approval_jobs),
        "version": "phaseA",
    }
