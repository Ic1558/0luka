"""Antigravity artifact engine - resolver only.

Reads the in-memory ArtifactStore and returns a structured decision.
No side effects. No subprocess. No file I/O. No live runtime mutation.
Approval gate remains NOT_APPROVED until explicitly lifted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from runtime.antigravity.state.artifact_store import ArtifactStore


@dataclass
class ResolvedDecision:
    """Outcome of artifact resolution pass."""

    can_proceed: bool
    blocking_ids: List[str] = field(default_factory=list)
    plan_ids: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    reason: str = ""


class ArtifactEngine:
    """Resolve runtime artifacts into a structured decision.

    Purely functional: reads store and returns decision with no mutation.
    """

    def __init__(self, store: ArtifactStore) -> None:
        self._store = store

    def resolve(self) -> ResolvedDecision:
        blockers = self._store.get_blockers()
        plans = self._store.get_plans()
        evidence = self._store.get_evidence()

        if blockers:
            return ResolvedDecision(
                can_proceed=False,
                blocking_ids=[blocker.blocker_id for blocker in blockers],
                plan_ids=[plan.plan_id for plan in plans],
                evidence_ids=[item.evidence_id for item in evidence],
                reason=f"{len(blockers)} blocker(s) present - execution not approved",
            )

        return ResolvedDecision(
            can_proceed=False,
            blocking_ids=[],
            plan_ids=[plan.plan_id for plan in plans],
            evidence_ids=[item.evidence_id for item in evidence],
            reason="no blockers - awaiting explicit approval gate lift",
        )
