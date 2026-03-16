"""AG-55: Governance Alert Policy.

Alert classes, severity mapping, and pure classification functions.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Alert classes
# ---------------------------------------------------------------------------

ALERT_CLASSES = [
    "CLAIM_MISMATCH_ALERT",
    "GOVERNANCE_INTEGRITY_BREAK",
    "HIGH_SENSITIVITY_RECOMMENDATION_ALERT",
    "TRUST_GAP_ALERT",
    "FEEDBACK_DIVERGENCE_ALERT",
]

# ---------------------------------------------------------------------------
# Alert severity
# ---------------------------------------------------------------------------

ALERT_SEVERITY_LEVELS = ["INFO", "WARNING", "HIGH", "CRITICAL"]

ALERT_CLASS_SEVERITY: dict[str, str] = {
    "CLAIM_MISMATCH_ALERT":                   "CRITICAL",
    "GOVERNANCE_INTEGRITY_BREAK":             "CRITICAL",
    "HIGH_SENSITIVITY_RECOMMENDATION_ALERT":  "HIGH",
    "TRUST_GAP_ALERT":                        "WARNING",
    "FEEDBACK_DIVERGENCE_ALERT":              "WARNING",
}

SEVERITY_ORDER: dict[str, int] = {
    "CRITICAL": 0,
    "HIGH":     1,
    "WARNING":  2,
    "INFO":     3,
}

# ---------------------------------------------------------------------------
# Pure classification functions
# ---------------------------------------------------------------------------


def severity_for_alert_class(alert_class: str) -> str:
    """Return severity level for a given alert class."""
    return ALERT_CLASS_SEVERITY.get(alert_class, "INFO")


def sort_alerts_by_severity(alerts: list[dict]) -> list[dict]:
    """Return alerts sorted by severity (CRITICAL first)."""
    return sorted(
        alerts,
        key=lambda a: SEVERITY_ORDER.get(a.get("severity", "INFO"), 99),
    )


def valid_alert_class(name: str) -> bool:
    return name in ALERT_CLASSES


def valid_severity_level(name: str) -> bool:
    return name in ALERT_SEVERITY_LEVELS
