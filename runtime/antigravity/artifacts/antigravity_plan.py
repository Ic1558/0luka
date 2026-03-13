"""Antigravity remediation plan artifact model.

Planning-layer model only. No execution logic, supervisor calls, or API calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class AntigravityPlan:
    """Structured plan object for remediation analysis and governance."""

    plan_id: str
    target_component: str
    blockers: List[str] = field(default_factory=list)
    proposed_actions: List[str] = field(default_factory=list)
    required_approvals: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    created_at: str = ""
