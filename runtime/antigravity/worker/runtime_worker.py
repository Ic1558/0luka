"""Antigravity runtime worker scaffolding.

Approval-gated stub. Does not execute subprocess, PM2, launchd, or external
APIs. Execution is gated on ApprovalState.APPROVED_WITH_CONDITIONS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from runtime.antigravity.artifacts.antigravity_blocker import AntigravityBlocker
from runtime.antigravity.artifacts.antigravity_plan import AntigravityPlan
from runtime.antigravity.executor.antigravity_runtime_executor import (
    AntigravityRuntimeExecutor,
    RuntimePhase,
)
from runtime.antigravity.runtime_state.antigravity_runtime_state import (
    AntigravityRuntimeState,
    ApprovalState,
)


@dataclass
class RuntimeWorkerResult:
    """Outcome record for a worker invocation attempt."""

    accepted: bool
    blockers: List[AntigravityBlocker] = field(default_factory=list)
    plan: Optional[AntigravityPlan] = None


class AntigravityRuntimeWorker:
    """Approval-gated worker stub for Antigravity runtime execution."""

    def __init__(
        self,
        executor: AntigravityRuntimeExecutor,
        state: AntigravityRuntimeState,
    ) -> None:
        self._executor = executor
        self._state = state
        self._phase_reference = RuntimePhase.EXECUTION_NOT_APPROVED

    def accept_job(self, job_id: str) -> RuntimeWorkerResult:
        """Accept a job while preserving approval and non-mutation boundaries."""
        if self._state.approval_state != ApprovalState.APPROVED_WITH_CONDITIONS:
            blocker = AntigravityBlocker(
                blocker_id=f"approval-gate-{job_id}",
                component="runtime_worker",
                description="execution approval is not granted",
                severity="BLOCKING",
                detected_at="",
            )
            return RuntimeWorkerResult(accepted=False, blockers=[blocker], plan=None)

        plan = AntigravityPlan(
            plan_id=f"plan-{job_id}",
            target_component="antigravity_runtime",
            proposed_actions=["verify_preconditions", "dispatch_worker_unit"],
        )
        return RuntimeWorkerResult(accepted=True, blockers=[], plan=plan)
