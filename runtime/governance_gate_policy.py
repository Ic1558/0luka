"""AG-52: Runtime Recommendation Governance Gate Policy.

Governance classes, review levels, and pure classification functions.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Governance classes
# ---------------------------------------------------------------------------

GOVERNANCE_CLASSES = [
    "LOW_SENSITIVITY",
    "MEDIUM_SENSITIVITY",
    "HIGH_SENSITIVITY",
    "CRITICAL_GOVERNANCE",
]

# ---------------------------------------------------------------------------
# Review levels
# ---------------------------------------------------------------------------

REVIEW_LEVELS = [
    "NO_REVIEW",
    "STANDARD_REVIEW",
    "GOVERNANCE_REVIEW",
    "CRITICAL_REVIEW",
]

# ---------------------------------------------------------------------------
# Governance class → review level mapping
# ---------------------------------------------------------------------------

GOVERNANCE_CLASS_TO_REVIEW_LEVEL: dict[str, str] = {
    "LOW_SENSITIVITY":   "NO_REVIEW",
    "MEDIUM_SENSITIVITY": "STANDARD_REVIEW",
    "HIGH_SENSITIVITY":  "GOVERNANCE_REVIEW",
    "CRITICAL_GOVERNANCE": "CRITICAL_REVIEW",
}

# ---------------------------------------------------------------------------
# Trust-class priority (used in classification)
# ---------------------------------------------------------------------------

_TRUST_CLASS_WEIGHT: dict[str, int] = {
    "HIGH_TRUST":        5,
    "TRUSTED_WITH_GAPS": 4,
    "CAUTION":           3,
    "LOW_TRUST":         2,
    "UNTRUSTED":         1,
    "":                  0,
}

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_governance_class(
    trust_class: str,
    confidence_class: str,
    gap_count: int,
) -> str:
    """Classify governance sensitivity for a recommendation.

    Rules (applied top-down, first match wins):
      HIGH_TRUST   + VERY_HIGH → LOW_SENSITIVITY
      TRUSTED_WITH_GAPS  or  gap_count <= 1  → MEDIUM_SENSITIVITY
      CAUTION  or  LOW_TRUST  → HIGH_SENSITIVITY
      UNTRUSTED  or  gap_count > 3  → CRITICAL_GOVERNANCE
    """
    if trust_class == "UNTRUSTED" or gap_count > 3:
        return "CRITICAL_GOVERNANCE"
    if trust_class in ("CAUTION", "LOW_TRUST"):
        return "HIGH_SENSITIVITY"
    if trust_class == "HIGH_TRUST" and confidence_class == "VERY_HIGH":
        return "LOW_SENSITIVITY"
    if trust_class == "TRUSTED_WITH_GAPS" or gap_count <= 1:
        return "MEDIUM_SENSITIVITY"
    # Fallback
    return "HIGH_SENSITIVITY"


def requires_governance_review(governance_class: str) -> bool:
    """Return True if the governance class requires a governance or critical review."""
    return governance_class in ("HIGH_SENSITIVITY", "CRITICAL_GOVERNANCE")


def requires_operator_review(governance_class: str) -> bool:
    """Return True if the governance class requires operator review."""
    return governance_class in ("HIGH_SENSITIVITY", "CRITICAL_GOVERNANCE")


def valid_governance_class(name: str) -> bool:
    """Return True if *name* is a valid governance class."""
    return name in GOVERNANCE_CLASSES
