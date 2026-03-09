"""Stub adapter for eventual 0luka policy integration.

Phase A intentionally fails closed to preserve governance boundaries.
"""

from __future__ import annotations


def check_approval(job: dict[str, object]) -> bool:
    """Fail closed: runtime policy checks are unavailable in phaseA stubs."""

    return False
