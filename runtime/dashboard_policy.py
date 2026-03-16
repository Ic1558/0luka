"""AG-56: Autonomous Supervision Dashboard Policy.

Dashboard section config, severity ordering, and summary ordering rules.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Dashboard sections
# ---------------------------------------------------------------------------

DASHBOARD_SECTIONS = [
    "runtime_identity",
    "readiness",
    "posture",
    "trust_index",
    "top_trust_gaps",
    "top_guidance_items",
    "open_decision_queue_summary",
    "governance_alerts",
    "integrity_breaks",
]

# ---------------------------------------------------------------------------
# Severity ordering for alerts (lower = higher priority)
# ---------------------------------------------------------------------------

SEVERITY_ORDER: dict[str, int] = {
    "CRITICAL": 0,
    "HIGH":     1,
    "WARNING":  2,
    "INFO":     3,
}

# ---------------------------------------------------------------------------
# Summary ordering rules
# ---------------------------------------------------------------------------

SUMMARY_SECTION_ORDER = [
    "governance_alerts",
    "integrity_breaks",
    "trust_index",
    "top_trust_gaps",
    "open_decision_queue_summary",
    "top_guidance_items",
    "runtime_identity",
    "readiness",
    "posture",
]

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def sort_alerts_by_severity(alerts: list[dict]) -> list[dict]:
    """Return alerts sorted by severity (CRITICAL first)."""
    return sorted(
        alerts,
        key=lambda a: SEVERITY_ORDER.get(a.get("severity", "INFO"), 99),
    )


def valid_section(name: str) -> bool:
    return name in DASHBOARD_SECTIONS
