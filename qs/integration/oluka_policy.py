"""Approval policy adapter boundary from qs into 0luka governance."""

from __future__ import annotations

from dataclasses import dataclass

from qs.app.jobs import JobContract


@dataclass(frozen=True)
class ApprovalDecision:
    approved: bool
    reason: str


class OlukaPolicyAdapter:
    """Thin policy adapter that fails closed until backed by 0luka approval APIs."""

    def check_approval(self, contract: JobContract) -> ApprovalDecision:
        if not contract.requires_approval:
            return ApprovalDecision(approved=True, reason="approval not required")
        return ApprovalDecision(approved=False, reason="approval backend not configured")
