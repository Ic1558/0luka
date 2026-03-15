"""AG-29: Policy Effectiveness Verification.

Measures whether a promoted policy actually improves runtime behaviour after
activation by comparing execution outcomes before vs after promotion.

Evidence sources (all read-only):
  - policy_activation_log.jsonl  — promotion timestamp per policy
  - learning_observations.jsonl  — per-run execution outcomes
  - policy_registry.json         — current status per policy

Verdicts:
  KEEP          — post-promotion outcomes measurably better than baseline
  REVIEW        — marginal improvement or short observation window
  ROLLBACK_RECOMMENDED — post-promotion outcomes worse than baseline
  INCONCLUSIVE  — not enough post-promotion observations (< MIN_OBSERVATIONS)

Output (read by policy_effectiveness_store):
  policy_effectiveness.json        latest effectiveness record per policy
  policy_verification_log.jsonl    append-only history

Safety invariants:
  - Read-only: never mutates registry or lifecycle state
  - Never auto-rollbacks — recommendations only
  - Fail-open: missing evidence → INCONCLUSIVE, not crash
"""
from __future__ import annotations

import time
from typing import Any

MIN_OBSERVATIONS: int = 3      # minimum post-promotion runs to emit non-INCONCLUSIVE verdict
ROLLBACK_THRESHOLD: float = 0.2   # failure rate delta that triggers ROLLBACK_RECOMMENDED
KEEP_THRESHOLD: float = 0.1       # failure rate delta (improvement) that triggers KEEP


# ---------------------------------------------------------------------------
# Evidence loaders (read-only)
# ---------------------------------------------------------------------------

def _load_activation_log() -> list[dict[str, Any]]:
    try:
        from core.policy.policy_registry import list_activation_log
        return list_activation_log(limit=500)
    except Exception:
        return []


def _load_observations() -> list[dict[str, Any]]:
    try:
        from learning.observation_store import get_recent_observations
        return get_recent_observations(limit=500)
    except Exception:
        return []


def _promoted_at(policy_id: str, activation_log: list[dict[str, Any]]) -> str | None:
    """Return the ISO timestamp when a policy was first ACTIVATED, or None."""
    for entry in activation_log:
        if entry.get("policy_id") == policy_id and entry.get("status") == "ACTIVATED":
            return str(entry.get("ts") or "")
    return None


def _failure_rate(observations: list[dict[str, Any]]) -> float:
    """Fraction of observations where execution_result ∈ {FAILED, PARTIAL}."""
    if not observations:
        return 0.0
    failures = sum(
        1 for o in observations
        if str(o.get("execution_result") or "").upper() in ("FAILED", "PARTIAL")
    )
    return failures / len(observations)


def _split_observations(
    observations: list[dict[str, Any]],
    promoted_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split observations into before/after the promotion timestamp."""
    before, after = [], []
    for obs in observations:
        ts = str(obs.get("timestamp") or "")
        if ts and ts < promoted_at:
            before.append(obs)
        elif ts and ts >= promoted_at:
            after.append(obs)
    return before, after


# ---------------------------------------------------------------------------
# Core verifier
# ---------------------------------------------------------------------------

def verify_policy_effectiveness(policy_id: str) -> dict[str, Any]:
    """Compute effectiveness verdict for one policy.

    Returns dict with:
      policy_id, verdict, baseline_failure_rate, post_failure_rate,
      delta, before_count, after_count, verified_at, reason.
    """
    verified_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    base: dict[str, Any] = {
        "policy_id": policy_id,
        "verdict": "INCONCLUSIVE",
        "baseline_failure_rate": None,
        "post_failure_rate": None,
        "delta": None,
        "before_count": 0,
        "after_count": 0,
        "verified_at": verified_at,
        "reason": "insufficient_evidence",
    }

    activation_log = _load_activation_log()
    promoted_at_ts = _promoted_at(policy_id, activation_log)
    if not promoted_at_ts:
        base["reason"] = "policy_not_found_in_activation_log"
        return base

    observations = _load_observations()
    if not observations:
        return base

    before, after = _split_observations(observations, promoted_at_ts)

    base["before_count"] = len(before)
    base["after_count"] = len(after)

    if len(after) < MIN_OBSERVATIONS:
        base["reason"] = f"only {len(after)} post-promotion observations (need {MIN_OBSERVATIONS})"
        return base

    baseline_rate = _failure_rate(before) if before else _failure_rate(observations)
    post_rate = _failure_rate(after)
    delta = post_rate - baseline_rate  # positive = worse, negative = better

    base["baseline_failure_rate"] = round(baseline_rate, 4)
    base["post_failure_rate"] = round(post_rate, 4)
    base["delta"] = round(delta, 4)

    if delta >= ROLLBACK_THRESHOLD:
        verdict = "ROLLBACK_RECOMMENDED"
        reason = f"failure_rate_increased_by_{abs(delta):.2%}"
    elif delta <= -KEEP_THRESHOLD:
        verdict = "KEEP"
        reason = f"failure_rate_reduced_by_{abs(delta):.2%}"
    else:
        verdict = "REVIEW"
        reason = f"marginal_change_{delta:+.2%}"

    base["verdict"] = verdict
    base["reason"] = reason
    return base


def verify_all_active_policies() -> list[dict[str, Any]]:
    """Run effectiveness verification for all ACTIVE policies.

    Returns list of effectiveness records.
    """
    try:
        from core.policy.policy_lifecycle import list_active_policies
        active = list_active_policies()
    except Exception:
        return []

    results = []
    for policy in active:
        policy_id = str(policy.get("policy_id") or "")
        if policy_id:
            results.append(verify_policy_effectiveness(policy_id))
    return results
