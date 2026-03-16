"""AG-31: Drift classifier — pure function classification of raw audit findings.

No I/O. No side effects. Deterministic given the same inputs.

Usage:
    from core.audit.drift_classifier import classify_finding, summarize_findings

    classified = [classify_finding(f) for f in raw_findings]
    summary = summarize_findings(classified)
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# All valid drift classes
DRIFT_CLASSES: frozenset[str] = frozenset({
    "expected_by_SOT_but_missing",
    "exists_but_not_wired",
    "active_but_not_canonical",
    "API_exposed_but_not_in_diagram",
    "canonical_component_but_no_runtime_evidence",
    "operator_gate_missing",
    "state_file_expected_but_not_produced",
    "naming_drift_only",
    "diagram_path_mismatch",
    "legacy_component_still_active",
    # Internal sentinel for unclassified findings
    "unknown",
})

# Severity levels (ordered lowest → highest)
SEVERITY_ORDER: list[str] = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
_SEVERITY_RANK: dict[str, int] = {s: i for i, s in enumerate(SEVERITY_ORDER)}

# Verdict levels (ordered lowest → highest severity)
VERDICT_ORDER: list[str] = ["CONSISTENT", "WIRED_WITH_GAPS", "DRIFT_DETECTED", "GOVERNANCE_VIOLATION"]
_VERDICT_RANK: dict[str, int] = {v: i for i, v in enumerate(VERDICT_ORDER)}

# Drift class → default severity mapping
_CLASS_DEFAULT_SEVERITY: dict[str, str] = {
    "expected_by_SOT_but_missing":              "HIGH",
    "exists_but_not_wired":                     "MEDIUM",
    "active_but_not_canonical":                 "MEDIUM",
    "API_exposed_but_not_in_diagram":           "LOW",
    "canonical_component_but_no_runtime_evidence": "MEDIUM",
    "operator_gate_missing":                    "CRITICAL",
    "state_file_expected_but_not_produced":     "MEDIUM",
    "naming_drift_only":                        "INFO",
    "diagram_path_mismatch":                    "INFO",
    "legacy_component_still_active":            "LOW",
    "unknown":                                  "LOW",
}

# Drift class → verdict contribution (when not suppressed by baseline)
_CLASS_VERDICT_IMPACT: dict[str, str] = {
    "expected_by_SOT_but_missing":              "DRIFT_DETECTED",
    "exists_but_not_wired":                     "WIRED_WITH_GAPS",
    "active_but_not_canonical":                 "WIRED_WITH_GAPS",
    "API_exposed_but_not_in_diagram":           "WIRED_WITH_GAPS",
    "canonical_component_but_no_runtime_evidence": "WIRED_WITH_GAPS",
    "operator_gate_missing":                    "GOVERNANCE_VIOLATION",
    "state_file_expected_but_not_produced":     "WIRED_WITH_GAPS",
    "naming_drift_only":                        "CONSISTENT",
    "diagram_path_mismatch":                    "CONSISTENT",
    "legacy_component_still_active":            "WIRED_WITH_GAPS",
    "unknown":                                  "WIRED_WITH_GAPS",
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def classify_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Classify a raw finding dict, returning an enriched dict.

    Input fields (required):
        drift_class   str   — one of DRIFT_CLASSES
        component     str   — human-readable component name or route
        evidence      str   — what was observed
        accepted      bool  — True if suppressed by known baseline

    Optional input fields:
        notes         str
        drift_key     str   — baseline key (for suppressed findings)

    Output adds:
        severity      str   — assigned severity
        verdict_impact str  — verdict contribution if unaccepted
        effective_verdict str — actual verdict contribution after acceptance
        status        str   — "OPEN" | "ACCEPTED"
    """
    result = dict(finding)

    drift_class = str(finding.get("drift_class") or "unknown")
    if drift_class not in DRIFT_CLASSES:
        drift_class = "unknown"
    result["drift_class"] = drift_class

    # Severity
    severity = _CLASS_DEFAULT_SEVERITY.get(drift_class, "LOW")
    # Allow override from finding (e.g. first-run optional state files → INFO)
    if "severity_override" in finding:
        override = str(finding["severity_override"]).upper()
        if override in _SEVERITY_RANK:
            severity = override
    result["severity"] = severity

    # Verdict impact
    verdict_impact = _CLASS_VERDICT_IMPACT.get(drift_class, "WIRED_WITH_GAPS")
    result["verdict_impact"] = verdict_impact

    # Status and effective verdict
    accepted = bool(finding.get("accepted", False))
    result["accepted"] = accepted
    result["status"] = "ACCEPTED" if accepted else "OPEN"

    if accepted:
        result["effective_verdict"] = "CONSISTENT"
    else:
        result["effective_verdict"] = verdict_impact

    return result


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate classified findings into a summary with an overall verdict.

    Returns:
        {
            "overall_verdict": str,
            "total": int,
            "open": int,
            "accepted": int,
            "counts": {"INFO": n, "LOW": n, "MEDIUM": n, "HIGH": n, "CRITICAL": n},
            "open_counts": {...},
            "blocking_drift": int,
        }
    """
    total = len(findings)
    open_findings = [f for f in findings if not f.get("accepted", False)]
    accepted_findings = [f for f in findings if f.get("accepted", False)]

    severity_counts: dict[str, int] = {s: 0 for s in SEVERITY_ORDER}
    open_severity_counts: dict[str, int] = {s: 0 for s in SEVERITY_ORDER}

    for f in findings:
        sev = str(f.get("severity", "LOW")).upper()
        if sev in severity_counts:
            severity_counts[sev] += 1

    for f in open_findings:
        sev = str(f.get("severity", "LOW")).upper()
        if sev in open_severity_counts:
            open_severity_counts[sev] += 1

    # Overall verdict = worst effective_verdict across all OPEN findings
    overall_verdict = "CONSISTENT"
    for f in open_findings:
        ev = str(f.get("effective_verdict", "CONSISTENT"))
        if ev in _VERDICT_RANK:
            if _VERDICT_RANK[ev] > _VERDICT_RANK[overall_verdict]:
                overall_verdict = ev

    # Blocking drift = open findings that push verdict to DRIFT_DETECTED or worse
    blocking_rank = _VERDICT_RANK["DRIFT_DETECTED"]
    blocking_drift = sum(
        1 for f in open_findings
        if _VERDICT_RANK.get(str(f.get("effective_verdict", "CONSISTENT")), 0) >= blocking_rank
    )

    return {
        "overall_verdict": overall_verdict,
        "total": total,
        "open": len(open_findings),
        "accepted": len(accepted_findings),
        "counts": severity_counts,
        "open_counts": open_severity_counts,
        "blocking_drift": blocking_drift,
    }


def compute_verdict(findings: list[dict[str, Any]]) -> str:
    """Convenience: compute just the overall verdict string from classified findings."""
    return summarize_findings(findings)["overall_verdict"]
