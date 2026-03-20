"""Worker adapter stub for unified runtime service interface."""

from __future__ import annotations

from runtime.antigravity.runtime_services.runtime_service_types import (
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)
from runtime.antigravity.worker.runtime_worker import AntigravityRuntimeWorker


class WorkerServiceAdapter:
    """Thin adapter around AntigravityRuntimeWorker."""

    def __init__(self, worker: AntigravityRuntimeWorker) -> None:
        self._worker = worker

    def handle(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        job_id = str(request.payload.get("job_id") or "runtime-service-job")
        outcome = self._worker.accept_job(job_id)
        return RuntimeExecutionResult(
            accepted=outcome.accepted,
            status="ACCEPTED" if outcome.accepted else "BLOCKED",
            message="worker adapter returns scaffold planning outcome only",
            data={
                "job_id": job_id,
                "blocker_ids": [item.blocker_id for item in outcome.blockers],
                "plan_id": outcome.plan.plan_id if outcome.plan else "",
            },
        )
