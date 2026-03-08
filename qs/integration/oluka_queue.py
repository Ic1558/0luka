"""Queue submission adapter boundary from qs into 0luka."""

from __future__ import annotations

from dataclasses import dataclass

from qs.app.jobs import JobContract


@dataclass(frozen=True)
class QueueSubmission:
    accepted: bool
    reason: str


class OlukaQueueAdapter:
    """Thin queue adapter that fails closed until wired to runtime transport."""

    def submit_job(self, contract: JobContract) -> QueueSubmission:
        del contract
        return QueueSubmission(accepted=False, reason="queue transport not configured")
