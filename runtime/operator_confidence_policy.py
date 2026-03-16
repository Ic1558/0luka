"""AG-51: Operator Confidence Calibration Policy.

Confidence classes, calibration dimensions, weights, and pure classification functions.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Confidence classes
# ---------------------------------------------------------------------------

CONFIDENCE_CLASSES = [
    "VERY_LOW",
    "LOW",
    "MODERATE",
    "HIGH",
    "VERY_HIGH",
]

# ---------------------------------------------------------------------------
# Calibration dimensions
# ---------------------------------------------------------------------------

CALIBRATION_DIMENSIONS = [
    "trust_alignment",
    "gap_severity",
    "claim_consistency",
    "readiness_match",
    "posture_alignment",
]

# ---------------------------------------------------------------------------
# Weights per dimension (must sum to 1.0)
# ---------------------------------------------------------------------------

WEIGHT_BY_DIMENSION: dict[str, float] = {
    "trust_alignment":   0.35,
    "gap_severity":      0.25,
    "claim_consistency": 0.20,
    "readiness_match":   0.10,
    "posture_alignment": 0.10,
}

# ---------------------------------------------------------------------------
# Dimension descriptions
# ---------------------------------------------------------------------------

DIMENSION_DESCRIPTIONS: dict[str, str] = {
    "trust_alignment":   "Alignment between runtime trust scores and operator expectations.",
    "gap_severity":      "Severity and count of identified trust gaps.",
    "claim_consistency": "Consistency of runtime claims with observed system state.",
    "readiness_match":   "Match between reported readiness level and operational posture.",
    "posture_alignment": "Alignment between declared posture and verified runtime behaviour.",
}

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_confidence(score: float) -> str:
    """Classify a confidence score into a confidence class.

    Thresholds:
      >= 0.85  VERY_HIGH
      >= 0.70  HIGH
      >= 0.50  MODERATE
      >= 0.30  LOW
      <  0.30  VERY_LOW
    """
    if score >= 0.85:
        return "VERY_HIGH"
    if score >= 0.70:
        return "HIGH"
    if score >= 0.50:
        return "MODERATE"
    if score >= 0.30:
        return "LOW"
    return "VERY_LOW"


def calibrate_dimension(dimension: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Calibrate a single dimension from provided evidence.

    Returns:
        {
            "dimension":        str,
            "score":            float,
            "confidence_class": str,
            "rationale":        str,
        }
    """
    if dimension not in CALIBRATION_DIMENSIONS:
        raise ValueError(f"Unknown calibration dimension: {dimension!r}")

    score: float = float(evidence.get("score", 0.5))
    # Clamp to [0.0, 1.0]
    score = max(0.0, min(1.0, score))
    confidence_class = classify_confidence(score)
    rationale = evidence.get(
        "rationale",
        DIMENSION_DESCRIPTIONS.get(dimension, "No rationale provided."),
    )
    return {
        "dimension":        dimension,
        "score":            score,
        "confidence_class": confidence_class,
        "rationale":        rationale,
    }


def valid_confidence_class(name: str) -> bool:
    """Return True if *name* is a valid confidence class."""
    return name in CONFIDENCE_CLASSES
