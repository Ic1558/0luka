"""Antigravity blocker artifact model.

Analysis-layer data model only. No runtime inspection or execution behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class AntigravityBlocker:
    """Structured blocker record for planning and remediation analysis."""

    blocker_id: str
    component: str
    description: str
    severity: str
    detected_at: str
    remediation_hint: str = ""
    evidence_refs: List[str] = field(default_factory=list)
