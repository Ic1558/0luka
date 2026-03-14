"""Antigravity runtime executor scaffolding.

This module is a safe preparation skeleton for supervised runtime execution.
It does not mutate live runtime, does not call supervisors, and does not call
external APIs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from core.policy.get_active_policy import get_active_policy
from runtime.antigravity.runtime_state.antigravity_runtime_state import (
    AntigravityRuntimeState,
    ApprovalState,
    RuntimePhase,
)

class AntigravityRuntimeExecutor:
    """Safe execution-prep controller for Antigravity runtime changes."""

    def __init__(self, policy_path: Path | None = None) -> None:
        self.state = AntigravityRuntimeState(
            phase=RuntimePhase.EXECUTION_NOT_APPROVED,
            approval_state=ApprovalState.NOT_APPROVED,
        )
        self.contract: Dict[str, str] = {}
        self.policy_path = policy_path

    def load_contract(self) -> Dict[str, str]:
        """Load contract metadata from local abstractions (stub)."""
        return self.contract

    def verify_preconditions(self) -> bool:
        """Verify preconditions without mutating runtime (stub)."""
        try:
            policy = get_active_policy(self.policy_path)
        except RuntimeError:
            self.state.blockers.append("policy_read_error")
            self.state.phase = RuntimePhase.BLOCKED
            self.state.policy_component = "defaults.freeze_state"
            self.state.policy_verdict = "blocked"
            return False

        self.state.policy_version = policy.version
        self.state.policy_component = "defaults.freeze_state"

        if policy.freeze_state:
            self.state.blockers.append("execution blocked by policy freeze")
            self.state.phase = RuntimePhase.BLOCKED
            self.state.freeze_state = True
            self.state.policy_verdict = "blocked"
            return False

        self.state.freeze_state = False
        self.state.policy_verdict = "pass"
        if self.state.approval_state != ApprovalState.APPROVED_WITH_CONDITIONS:
            self.state.blockers.append("execution approval is not granted")
            self.state.phase = RuntimePhase.BLOCKED
            return False
        return True

    def build_execution_plan(self) -> Dict[str, object]:
        """Build a supervised plan artifact without executing actions (stub)."""
        return {
            "phase": self.state.phase.value,
            "approval_state": self.state.approval_state.value,
            "steps": [],
            "blockers": list(self.state.blockers),
        }

    def report_blockers(self) -> List[str]:
        """Return blocker messages for governance reporting."""
        return list(self.state.blockers)
