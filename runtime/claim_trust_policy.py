"""AG-49: Claim Trust Index Policy.

Trust class thresholds, score weights, and helper functions.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Trust classes (ordered worst → best)
# ---------------------------------------------------------------------------

TRUST_CLASSES = ["UNTRUSTED", "LOW_TRUST", "CAUTION", "TRUSTED_WITH_GAPS", "HIGH_TRUST"]

TRUST_CLASS_THRESHOLDS: dict[str, float] = {
    "HIGH_TRUST":        0.90,   # score >= 0.90
    "TRUSTED_WITH_GAPS": 0.70,   # score >= 0.70
    "CAUTION":           0.50,   # score >= 0.50
    "LOW_TRUST":         0.25,   # score >= 0.25
    "UNTRUSTED":         0.0,    # < 0.25
}

# ---------------------------------------------------------------------------
# Claim group weights for overall trust index
# ---------------------------------------------------------------------------

CLAIM_GROUP_WEIGHTS: dict[str, float] = {
    "identity":  0.25,   # identity claims matter but are more static
    "readiness": 0.40,   # readiness is high-signal
    "posture":   0.35,   # posture reflects live operational state
}

# ---------------------------------------------------------------------------
# Verdict weights for score calculation
# ---------------------------------------------------------------------------

VERDICT_WEIGHTS: dict[str, float] = {
    "VERIFIED":     1.0,
    "INCONCLUSIVE": 0.5,
    "UNSUPPORTED":  0.2,
    "INCONSISTENT": 0.0,
}

# ---------------------------------------------------------------------------
# Gap severity mapping
# ---------------------------------------------------------------------------

GAP_SEVERITY: dict[str, str] = {
    "inconsistent_claim":           "HIGH",
    "unsupported_claim":            "MEDIUM",
    "posture_mismatch":             "HIGH",
    "readiness_overclaim":          "HIGH",
    "capability_count_mismatch":    "HIGH",
    "operating_mode_mismatch":      "HIGH",
    "inconclusive_claim":           "LOW",
}


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def valid_trust_class(name: str) -> bool:
    """Return True if name is a registered trust class."""
    return name in TRUST_CLASSES


def classify_trust(score: float) -> str:
    """Return trust class for a given score [0.0, 1.0]."""
    if score >= TRUST_CLASS_THRESHOLDS["HIGH_TRUST"]:
        return "HIGH_TRUST"
    if score >= TRUST_CLASS_THRESHOLDS["TRUSTED_WITH_GAPS"]:
        return "TRUSTED_WITH_GAPS"
    if score >= TRUST_CLASS_THRESHOLDS["CAUTION"]:
        return "CAUTION"
    if score >= TRUST_CLASS_THRESHOLDS["LOW_TRUST"]:
        return "LOW_TRUST"
    return "UNTRUSTED"


def weighted_claim_group_score(
    verified: int,
    inconsistent: int,
    unsupported: int,
    inconclusive: int,
) -> float:
    """Compute a weighted score [0.0, 1.0] for a claim group.

    VERIFIED = 1.0, INCONCLUSIVE = 0.5, UNSUPPORTED = 0.2, INCONSISTENT = 0.0.
    Returns 0.0 if no claims.
    """
    total = verified + inconsistent + unsupported + inconclusive
    if total == 0:
        return 0.0
    raw = (
        verified     * VERDICT_WEIGHTS["VERIFIED"]
        + inconclusive * VERDICT_WEIGHTS["INCONCLUSIVE"]
        + unsupported  * VERDICT_WEIGHTS["UNSUPPORTED"]
        + inconsistent * VERDICT_WEIGHTS["INCONSISTENT"]
    )
    return round(raw / total, 4)
