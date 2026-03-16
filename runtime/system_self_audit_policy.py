"""AG-57: System Self-Audit Policy.

Audit verdict classes, coherence checks, and required artifact map.
Pure data + pure functions — no I/O, no side effects.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Audit verdict classes
# ---------------------------------------------------------------------------

AUDIT_VERDICTS = [
    "STACK_COHERENT",
    "STACK_WITH_GAPS",
    "STACK_INCONSISTENT",
    "STACK_UNTRUSTED",
]

# ---------------------------------------------------------------------------
# Required artifact map (AG-47 through AG-56)
# ---------------------------------------------------------------------------

REQUIRED_ARTIFACTS: dict[str, list[str]] = {
    "AG-47 self_awareness":  ["runtime_self_awareness_latest.json"],
    "AG-49 claim_trust":     ["runtime_claim_trust_latest.json", "runtime_claim_trust_index.json"],
    "AG-50 trust_guidance":  ["runtime_trust_guidance_latest.json"],
    "AG-51 confidence":      ["runtime_operator_confidence_latest.json"],
    "AG-52 governance_gate": ["runtime_governance_gate_latest.json"],
    "AG-53 integrity":       ["runtime_operator_decision_integrity_latest.json"],
    "AG-54 feedback":        ["runtime_recommendation_feedback_latest.json"],
    "AG-55 alerts":          ["runtime_governance_alerts_latest.json"],
    "AG-56 dashboard":       ["runtime_supervision_dashboard_latest.json"],
}

# ---------------------------------------------------------------------------
# Coherence checks
# ---------------------------------------------------------------------------

COHERENCE_CHECKS = [
    "self_awareness_present",
    "trust_index_present",
    "guidance_present",
    "governance_gate_present",
    "integrity_present",
    "alerts_present",
    "dashboard_present",
]

# ---------------------------------------------------------------------------
# Verdict derivation rules
# ---------------------------------------------------------------------------

def derive_verdict(
    missing_count: int,
    incoherent_count: int,
    total_checks: int,
) -> str:
    """Derive audit verdict from missing artifact and coherence failure counts."""
    if missing_count == 0 and incoherent_count == 0:
        return "STACK_COHERENT"
    if missing_count <= 2 and incoherent_count <= 1:
        return "STACK_WITH_GAPS"
    if missing_count <= 4:
        return "STACK_INCONSISTENT"
    return "STACK_UNTRUSTED"


def valid_verdict(name: str) -> bool:
    return name in AUDIT_VERDICTS
