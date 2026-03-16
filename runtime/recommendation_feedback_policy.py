"""AG-54: Recommendation Feedback Policy.

Feedback classes, outcome mappings, and pure classification functions.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Feedback classes
# ---------------------------------------------------------------------------

FEEDBACK_CLASSES = [
    "FOLLOWED",
    "DEFERRED",
    "OVERRIDDEN",
    "IGNORED",
    "INCONCLUSIVE",
]

# ---------------------------------------------------------------------------
# Decision status → feedback outcome mapping
# ---------------------------------------------------------------------------

DECISION_STATUS_TO_FEEDBACK: dict[str, str] = {
    "APPROVED":   "FOLLOWED",
    "FOLLOWED":   "FOLLOWED",
    "DEFERRED":   "DEFERRED",
    "PENDING":    "DEFERRED",
    "OPEN":       "DEFERRED",
    "OVERRIDDEN": "OVERRIDDEN",
    "REJECTED":   "OVERRIDDEN",
    "DENIED":     "OVERRIDDEN",
    "IGNORED":    "IGNORED",
    "EXPIRED":    "IGNORED",
    "CLOSED":     "INCONCLUSIVE",
}

# ---------------------------------------------------------------------------
# Severity of feedback divergence
# ---------------------------------------------------------------------------

FEEDBACK_DIVERGENCE_SEVERITY: dict[str, str] = {
    "FOLLOWED":    "NONE",
    "DEFERRED":    "LOW",
    "OVERRIDDEN":  "HIGH",
    "IGNORED":     "HIGH",
    "INCONCLUSIVE": "MEDIUM",
}

# ---------------------------------------------------------------------------
# Pure classification functions
# ---------------------------------------------------------------------------


def feedback_class_for_decision_status(status: str) -> str:
    """Return feedback class for a given operator decision status."""
    return DECISION_STATUS_TO_FEEDBACK.get(status.upper() if status else "", "INCONCLUSIVE")


def divergence_severity_for_feedback(feedback_class: str) -> str:
    """Return divergence severity for a feedback class."""
    return FEEDBACK_DIVERGENCE_SEVERITY.get(feedback_class, "MEDIUM")


def valid_feedback_class(name: str) -> bool:
    return name in FEEDBACK_CLASSES
