"""Local Antigravity runtime state model for Phase R1 scaffolding.

This module defines in-memory state structures only. It performs no live
inspection, no supervisor calls, and no file I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class RuntimePhase(str, Enum):
    """Runtime phase gate states for Antigravity execution prep."""

    IDLE = "IDLE"
    PREPARED = "PREPARED"
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"
    EXECUTION_NOT_APPROVED = "EXECUTION_NOT_APPROVED"


class ApprovalState(str, Enum):
    """Approval state for runtime mutation."""

    NOT_APPROVED = "NOT_APPROVED"
    APPROVED_WITH_CONDITIONS = "APPROVED_WITH_CONDITIONS"
    DENIED = "DENIED"


@dataclass
class AntigravityRuntimeState:
    """In-memory local state for safe execution planning."""

    phase: RuntimePhase = RuntimePhase.EXECUTION_NOT_APPROVED
    approval_state: ApprovalState = ApprovalState.NOT_APPROVED
    blockers: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    working_directory: str = ""
    canonical_entrypoint: str = "modules/antigravity/realtime/control_tower.py"
    policy_version: str = ""
    policy_component: str = ""
    policy_verdict: str = ""
    freeze_state: bool = False
