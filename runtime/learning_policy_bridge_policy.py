"""AG-67: Learning-to-policy bridge policy."""
READINESS_THRESHOLDS = {"READY": 0.8, "REVIEW": 0.5}


def score_readiness(confidence: float) -> str:
    if confidence >= READINESS_THRESHOLDS["READY"]:
        return "READY"
    elif confidence >= READINESS_THRESHOLDS["REVIEW"]:
        return "REVIEW"
    return "NOT_READY"
