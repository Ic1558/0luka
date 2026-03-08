"""Status publish adapter boundary from qs into 0luka status channels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatusPublishResult:
    published: bool
    reason: str


class OlukaStatusAdapter:
    """Thin status adapter that fails closed until output channel is configured."""

    def publish_status(self, payload: dict[str, object]) -> StatusPublishResult:
        del payload
        return StatusPublishResult(published=False, reason="status channel not configured")
