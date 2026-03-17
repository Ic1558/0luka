"""Executor adapter stub for unified runtime service interface."""

from __future__ import annotations

from runtime.antigravity.executor.antigravity_runtime_executor import (
    AntigravityRuntimeExecutor,
)
from runtime.antigravity.runtime_services.runtime_service_types import (
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
)


class ExecutorServiceAdapter:
    """Thin adapter around AntigravityRuntimeExecutor."""

    def __init__(self, executor: AntigravityRuntimeExecutor) -> None:
        self._executor = executor

    def handle(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        plan = self._executor.build_execution_plan()
        return RuntimeExecutionResult(
            accepted=False,
            status="SCaffold_PLAN_ONLY".upper(),
            message="executor adapter is scaffold-only and does not execute runtime mutations",
            data={"action": request.action, "plan": plan},
        )
