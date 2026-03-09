"""Stub adapter for eventual 0luka queue integration.

Phase A intentionally avoids live runtime coupling. This module only exposes
safe defaults and deterministic signatures.
"""

from __future__ import annotations


def submit_job(job: dict[str, object]) -> dict[str, object]:
    """Return a deterministic stub response without contacting runtime queues."""

    return {
        "accepted": False,
        "status": "stubbed",
        "reason": "0luka queue integration is not enabled in phaseA",
        "job_type": job.get("job_type"),
    }
