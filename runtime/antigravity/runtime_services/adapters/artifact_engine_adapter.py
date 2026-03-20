"""Artifact engine adapter stub for unified runtime service interface."""

from __future__ import annotations

from runtime.antigravity.engine.artifact_engine import ArtifactEngine
from runtime.antigravity.runtime_services.runtime_service_types import (
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)


class ArtifactEngineServiceAdapter:
    """Thin adapter around ArtifactEngine resolver."""

    def __init__(self, artifact_engine: ArtifactEngine) -> None:
        self._artifact_engine = artifact_engine

    def handle(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        decision = self._artifact_engine.resolve()
        return RuntimeExecutionResult(
            accepted=False,
            status="RESOLVED",
            message="artifact engine adapter returns resolution only",
            data={
                "action": request.action,
                "can_proceed": decision.can_proceed,
                "blocking_ids": list(decision.blocking_ids),
                "plan_ids": list(decision.plan_ids),
                "evidence_ids": list(decision.evidence_ids),
                "reason": decision.reason,
            },
        )
