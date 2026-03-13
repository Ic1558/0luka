"""Antigravity artifact store - in-memory only.

No file I/O, no persistence, no subprocess calls, and no live runtime
inspection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from runtime.antigravity.artifacts.antigravity_blocker import AntigravityBlocker
from runtime.antigravity.artifacts.antigravity_evidence import AntigravityEvidence
from runtime.antigravity.artifacts.antigravity_plan import AntigravityPlan


@dataclass
class ArtifactStore:
    """In-memory store for runtime analysis artifacts."""

    blockers: List[AntigravityBlocker] = field(default_factory=list)
    evidence: List[AntigravityEvidence] = field(default_factory=list)
    plans: List[AntigravityPlan] = field(default_factory=list)

    def add_blocker(self, b: AntigravityBlocker) -> None:
        self.blockers.append(b)

    def add_evidence(self, e: AntigravityEvidence) -> None:
        self.evidence.append(e)

    def add_plan(self, p: AntigravityPlan) -> None:
        self.plans.append(p)

    def has_blockers(self) -> bool:
        return len(self.blockers) > 0

    def get_blockers(self) -> List[AntigravityBlocker]:
        return list(self.blockers)

    def get_evidence(self) -> List[AntigravityEvidence]:
        return list(self.evidence)

    def get_plans(self) -> List[AntigravityPlan]:
        return list(self.plans)
