"""Antigravity runtime engine - artifact emitter only.

Emits blocker, evidence, and plan artifacts to the in-memory store.
No subprocess calls, no file I/O, no live runtime mutation.
Approval gate remains at NOT_APPROVED until explicitly lifted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from runtime.antigravity.artifacts.antigravity_blocker import AntigravityBlocker
from runtime.antigravity.artifacts.antigravity_evidence import AntigravityEvidence
from runtime.antigravity.artifacts.antigravity_plan import AntigravityPlan
from runtime.antigravity.state.artifact_store import ArtifactStore


class AntigravityRuntimeEngine:
    """Emit runtime artifacts to the in-memory store.

    Does not execute runtime actions and does not approve execution.
    """

    def __init__(self, store: ArtifactStore) -> None:
        self._store = store

    def emit_blocker(
        self,
        blocker_id: str,
        component: str,
        description: str,
        severity: str,
        remediation_hint: str = "",
    ) -> AntigravityBlocker:
        blocker = AntigravityBlocker(
            blocker_id=blocker_id,
            component=component,
            description=description,
            severity=severity,
            detected_at=_now(),
            remediation_hint=remediation_hint,
        )
        self._store.add_blocker(blocker)
        return blocker

    def emit_evidence(
        self,
        evidence_id: str,
        evidence_type: str,
        source: str,
        reference_path: str,
        notes: str = "",
    ) -> AntigravityEvidence:
        evidence = AntigravityEvidence(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            source=source,
            timestamp=_now(),
            reference_path=reference_path,
            notes=notes,
        )
        self._store.add_evidence(evidence)
        return evidence

    def emit_plan(
        self,
        plan_id: str,
        target_component: str,
        blockers: Optional[List[str]] = None,
        proposed_actions: Optional[List[str]] = None,
        required_approvals: Optional[List[str]] = None,
        evidence_refs: Optional[List[str]] = None,
    ) -> AntigravityPlan:
        plan = AntigravityPlan(
            plan_id=plan_id,
            target_component=target_component,
            blockers=blockers or [],
            proposed_actions=proposed_actions or [],
            required_approvals=required_approvals or [],
            evidence_refs=evidence_refs or [],
            created_at=_now(),
        )
        self._store.add_plan(plan)
        return plan


def _now() -> str:
    """Return UTC timestamp for artifact metadata."""
    return datetime.now(timezone.utc).isoformat()
