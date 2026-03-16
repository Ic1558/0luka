"""AG-50: Trust-Aware Operator Guidance Policy.

Guidance modes, caution classes, override types, and pure classification functions.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Guidance modes
# ---------------------------------------------------------------------------

GUIDANCE_MODES = [
    "TRUST_ALIGNED",
    "TRUST_WITH_CAUTION",
    "LIMITED_TRUST_GUIDANCE",
    "HIGH_SCRUTINY",
    "CLAIM_MISMATCH_ALERT",
]

# ---------------------------------------------------------------------------
# Caution classes
# ---------------------------------------------------------------------------

CAUTION_CLASSES = [
    "NO_CAUTION",
    "LOW_CAUTION",
    "MODERATE_CAUTION",
    "HIGH_CAUTION",
    "CRITICAL_CAUTION",
]

# ---------------------------------------------------------------------------
# Override types
# ---------------------------------------------------------------------------

OVERRIDE_TYPES = [
    "NO_OVERRIDE",
    "TRUST_SCORE_OVERRIDE",
    "GAP_SEVERITY_OVERRIDE",
    "CLAIM_MISMATCH_OVERRIDE",
    "OPERATOR_FORCED_OVERRIDE",
]

# ---------------------------------------------------------------------------
# Trust-class to guidance mode mapping
# ---------------------------------------------------------------------------

TRUST_CLASS_TO_GUIDANCE_MODE: dict[str, str] = {
    "HIGH_TRUST":        "TRUST_ALIGNED",
    "TRUSTED_WITH_GAPS": "TRUST_WITH_CAUTION",
    "CAUTION":           "LIMITED_TRUST_GUIDANCE",
    "LOW_TRUST":         "HIGH_SCRUTINY",
    "UNTRUSTED":         "CLAIM_MISMATCH_ALERT",
}

# ---------------------------------------------------------------------------
# Guidance mode descriptions
# ---------------------------------------------------------------------------

GUIDANCE_MODE_DESCRIPTIONS: dict[str, str] = {
    "TRUST_ALIGNED":       "Runtime claims well-supported. Standard operator review applies.",
    "TRUST_WITH_CAUTION":  "Runtime claims mostly supported. Review identified gaps before acting.",
    "LIMITED_TRUST_GUIDANCE": "Trust gaps detected. Treat guidance with caution; verify claims independently.",
    "HIGH_SCRUTINY":       "Multiple unsupported claims. Apply manual verification before trusting guidance.",
    "CLAIM_MISMATCH_ALERT": "Runtime claims cannot be trusted. Operator must perform manual state inspection.",
}

# ---------------------------------------------------------------------------
# Caution class thresholds (driven by gap_count and trust_score)
# ---------------------------------------------------------------------------

def classify_caution(trust_score: float, gap_count: int) -> str:
    """Classify caution level based on trust score and gap count."""
    if trust_score >= 0.90 and gap_count == 0:
        return "NO_CAUTION"
    if trust_score >= 0.70 and gap_count <= 1:
        return "LOW_CAUTION"
    if trust_score >= 0.50 and gap_count <= 3:
        return "MODERATE_CAUTION"
    if trust_score >= 0.25:
        return "HIGH_CAUTION"
    return "CRITICAL_CAUTION"


def guidance_mode_for_trust_class(trust_class: str) -> str:
    """Return guidance mode for a given trust class."""
    return TRUST_CLASS_TO_GUIDANCE_MODE.get(trust_class, "CLAIM_MISMATCH_ALERT")


def valid_guidance_mode(name: str) -> bool:
    return name in GUIDANCE_MODES


def valid_caution_class(name: str) -> bool:
    return name in CAUTION_CLASSES


def valid_override_type(name: str) -> bool:
    return name in OVERRIDE_TYPES


def guidance_description(mode: str) -> str:
    return GUIDANCE_MODE_DESCRIPTIONS.get(mode, "No description available.")
