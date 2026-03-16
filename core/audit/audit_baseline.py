"""AG-31: Known accepted drift baseline.

Encodes drift items that have been reviewed and accepted. AG-31 suppresses
these from BLOCKING verdict — they appear in the audit report as ACCEPTED
rather than OPEN findings.

Update this file when a new drift item is reviewed and explicitly accepted.
Never add items here to hide real problems; add only items with a documented
rationale and architectural owner.

All baseline data is read-only at runtime — deterministic lookup only.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Known accepted drift
# ---------------------------------------------------------------------------

KNOWN_ACCEPTED_DRIFT: dict[str, dict[str, str]] = {
    "runtime_guardian_name_gap": {
        "description": (
            "SOT and architecture diagram reference 'runtime_guardian' as a named component. "
            "No file core/runtime_guardian.py exists. The function is fulfilled by "
            "core/circuit_breaker.py (trip/reset logic) + core/phase1a_resolver.py (inbound gate). "
            "Naming drift only — capability is fully present."
        ),
        "drift_class": "naming_drift_only",
        "severity": "INFO",
        "owner": "CLC",
        "accepted_at": "2026-03-16",
    },
    "api_activity_name_gap": {
        "description": (
            "Architecture diagram references 'api_activity.py' as an endpoint module. "
            "No file interface/operator/api_activity.py exists. Activity data is served "
            "by interface/operator/api_decisions.py and the /api/activity route in "
            "mission_control_server.py. Naming drift only — route is live."
        ),
        "drift_class": "naming_drift_only",
        "severity": "INFO",
        "owner": "CLC",
        "accepted_at": "2026-03-16",
    },
    "feedback_loop_lazy_path": {
        "description": (
            "core/orchestrator/feedback_loop.py is wired into the runtime via "
            "tools/ops/sovereign_loop.py:247 (lazy import at runtime startup). "
            "It is not imported directly by core/task_dispatcher.py or core/router.py. "
            "Architecture diagram shows it in Layer 7. The wiring path is intentional — "
            "sovereign_loop is the canonical entrypoint for the feedback loop. "
            "Not a missing wiring; a non-obvious wiring path."
        ),
        "drift_class": "diagram_path_mismatch",
        "severity": "INFO",
        "owner": "CLC",
        "accepted_at": "2026-03-16",
    },
    "legacy_remediation_parallel_path": {
        "description": (
            "core/remediation_engine.py (legacy path, pre-AG-20) coexists with "
            "core/adaptation/adaptation_engine.py (canonical AG-20 path). "
            "The legacy module is still imported by some routes and is not removed. "
            "Both paths are active. This is accepted as a migration-in-progress state, "
            "not a governance violation."
        ),
        "drift_class": "legacy_component_still_active",
        "severity": "LOW",
        "owner": "CLC",
        "accepted_at": "2026-03-16",
    },
    "first_run_optional_state_files": {
        "description": (
            "Several state files under $LUKA_RUNTIME_ROOT/state/ are created on first use "
            "and will be absent on a fresh runtime root. These include: "
            "learning_observations.jsonl (AG-21), policy_outcome_governance.jsonl (AG-30), "
            "effectiveness_store state (AG-29). Absence is correct first-run behavior and "
            "should be classified as INFO, not DRIFT_DETECTED."
        ),
        "drift_class": "state_file_expected_but_not_produced",
        "severity": "INFO",
        "owner": "CLC",
        "accepted_at": "2026-03-16",
    },
}

# State files that are first-run optional (absence = INFO, not drift)
FIRST_RUN_OPTIONAL_STATE_FILES: frozenset[str] = frozenset({
    "learning_observations.jsonl",
    "policy_outcome_governance.jsonl",
    "policy_outcome_latest.json",
    "effectiveness_store.json",
    "pattern_registry.json",
    "policy_candidates.json",
})

# Drift keys that belong to the accepted drift baseline
_ACCEPTED_KEYS: frozenset[str] = frozenset(KNOWN_ACCEPTED_DRIFT.keys())


def is_known_drift(drift_key: str) -> bool:
    """Return True if this drift_key is in the accepted baseline."""
    return drift_key in _ACCEPTED_KEYS


def get_known_drift_reason(drift_key: str) -> str | None:
    """Return the documented rationale for an accepted drift item, or None."""
    entry = KNOWN_ACCEPTED_DRIFT.get(drift_key)
    if entry is None:
        return None
    return entry.get("description")


def is_first_run_optional(state_filename: str) -> bool:
    """Return True if absent state file is acceptable on a fresh runtime."""
    return state_filename in FIRST_RUN_OPTIONAL_STATE_FILES
