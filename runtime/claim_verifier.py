"""AG-48: Runtime Claim Verifier.

Verifies that runtime self-awareness claims (from AG-47) are supported
by actual runtime evidence — capability envelope, governance state,
campaign state, and strategy state.

Verification-only — no governance mutation, no campaign mutation,
no repair execution, no baseline mutation, no automatic claim correction,
no capability activation.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from runtime.claim_verifier_policy import (
    CANONICAL_RUNTIME_ROLE,
    CANONICAL_SYSTEM_IDENTITY,
    verify_posture_rule,
    verify_readiness_rule,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rt(runtime_root: str | None = None) -> str:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    return rt


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rows.append(json.loads(raw))
        except Exception:
            continue
    return rows


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_self_awareness(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-47 self-awareness artifacts."""
    rt = _rt(runtime_root)
    latest   = _read_json(Path(rt) / "state" / "runtime_self_awareness_latest.json") or {}
    readiness = _read_json(Path(rt) / "state" / "runtime_readiness.json") or {}
    return {
        "latest":    latest,
        "readiness": readiness,
        "identity":  latest.get("identity", {}),
        "posture":   latest.get("posture", {}),
        "present":   bool(latest),
    }


def load_capability_envelope(runtime_root: str | None = None) -> dict[str, Any]:
    """Load actual capability state from AG-46."""
    rt = _rt(runtime_root)
    try:
        from runtime.capability_registry import list_active_capabilities, registry_summary
        active  = list_active_capabilities(rt)
        summary = registry_summary(rt)
    except Exception:
        active  = []
        summary = {"total_registered": 0, "active_count": 0, "active": [], "all": []}
    return {
        "active_capabilities": active,
        "active_count":        len(active),
        "summary":             summary,
    }


def load_runtime_strategy(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-42 strategy state."""
    rt = _rt(runtime_root)
    strategy  = _read_json(Path(rt) / "state" / "runtime_strategy_latest.json") or {}
    mode_data = _read_json(Path(rt) / "state" / "runtime_operating_mode.json") or {}
    return {
        "operating_mode":  mode_data.get("operating_mode") or strategy.get("operating_mode"),
        "strategy_present": bool(strategy),
        "key_risks":       strategy.get("key_risks", []),
    }


def load_governance_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-31/AG-32/AG-44 governance state."""
    rt = _rt(runtime_root)
    findings  = _read_json(Path(rt) / "state" / "drift_finding_status.json") or {}
    gov_log   = _read_jsonl(Path(rt) / "state" / "drift_governance_log.jsonl")
    queue     = _read_json(Path(rt) / "state" / "decision_queue_governance_latest.json") or {}
    return {
        "governance_present":     bool(findings or gov_log or queue),
        "findings_count":         len(findings),
        "queue_governance_present": bool(queue),
        "operator_action_required": queue.get("operator_action_required", False),
    }


def load_campaign_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-34/AG-40/AG-41 campaign state."""
    rt = _rt(runtime_root)
    campaign = _read_json(Path(rt) / "state" / "repair_campaign_latest.json") or {}
    wave     = _read_json(Path(rt) / "state" / "repair_wave_latest.json") or {}
    outcome  = _read_json(Path(rt) / "state" / "repair_campaign_outcome_latest.json") or {}
    return {
        "campaign_present":      bool(campaign or wave),
        "outcome_intel_present": bool(outcome),
    }


def load_decision_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-43/AG-44/AG-45 decision state."""
    rt = _rt(runtime_root)
    decision = _read_json(Path(rt) / "state" / "operator_decision_latest.json") or {}
    q_state  = _read_json(Path(rt) / "state" / "decision_queue_state.json") or {}
    memory   = _read_json(Path(rt) / "state" / "operator_decision_memory_latest.json") or {}
    return {
        "decision_assist_present": bool(decision),
        "queue_state_present":     bool(q_state),
        "memory_present":          bool(memory),
    }


def load_repair_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-33/AG-35/AG-38 repair state."""
    rt = _rt(runtime_root)
    plan    = _read_json(Path(rt) / "state" / "drift_repair_plan_latest.json") or {}
    exec_log = _read_jsonl(Path(rt) / "state" / "drift_repair_execution_log.jsonl")
    return {
        "repair_plan_present":        bool(plan),
        "repair_execution_available": bool(plan or exec_log),
        "execution_count":            len(exec_log),
    }


# ---------------------------------------------------------------------------
# Claim verification functions
# ---------------------------------------------------------------------------

def verify_identity_claims(
    self_awareness: dict[str, Any],
    capability_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Verify identity-level claims from AG-47.

    Checks:
    1. system_identity is canonical
    2. runtime_role is canonical
    3. active_capability_count matches actual envelope
    """
    identity = self_awareness.get("identity", {})
    results: list[dict[str, Any]] = []

    # 1. system_identity
    claimed_identity = identity.get("system_identity", "")
    results.append({
        "claim_class":    "identity",
        "claim_key":      "system_identity",
        "claimed_value":  claimed_identity,
        "observed_value": CANONICAL_SYSTEM_IDENTITY,
        "verdict":        "VERIFIED" if claimed_identity == CANONICAL_SYSTEM_IDENTITY else "INCONSISTENT",
        "evidence_refs":  ["runtime/self_awareness.py"],
    })

    # 2. runtime_role
    claimed_role = identity.get("runtime_role", "")
    results.append({
        "claim_class":    "identity",
        "claim_key":      "runtime_role",
        "claimed_value":  claimed_role,
        "observed_value": CANONICAL_RUNTIME_ROLE,
        "verdict":        "VERIFIED" if claimed_role == CANONICAL_RUNTIME_ROLE else (
            "UNSUPPORTED" if not claimed_role else "INCONSISTENT"
        ),
        "evidence_refs":  ["runtime/self_awareness.py"],
    })

    # 3. active_capability_count — claim vs envelope
    claimed_count  = int(identity.get("active_capability_count", -1))
    observed_count = capability_data.get("active_count", 0)

    if claimed_count == -1:
        # No claim made — unsupported
        verdict = "UNSUPPORTED"
    elif claimed_count == observed_count:
        verdict = "VERIFIED"
    else:
        verdict = "INCONSISTENT"

    results.append({
        "claim_class":    "identity",
        "claim_key":      "active_capability_count",
        "claimed_value":  claimed_count if claimed_count != -1 else None,
        "observed_value": observed_count,
        "verdict":        verdict,
        "evidence_refs":  ["runtime_capabilities.jsonl"],
    })

    return results


def verify_readiness_claims(
    self_awareness: dict[str, Any],
    capability_data: dict[str, Any],
    strategy_data: dict[str, Any],
    governance_data: dict[str, Any],
    repair_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Verify readiness claims from AG-47."""
    readiness_data = self_awareness.get("readiness", {})
    claimed = readiness_data.get("readiness") or self_awareness.get("latest", {}).get(
        "readiness", {}
    ).get("readiness")

    if not claimed:
        return [{
            "claim_class": "readiness",
            "claim_key":   "readiness",
            "claimed_value": None,
            "verdict":     "UNSUPPORTED",
            "reason":      "no readiness claim found in self-awareness artifacts",
            "evidence_refs": ["runtime_self_awareness_latest.json"],
        }]

    evidence = {
        "active_capability_count": capability_data.get("active_count", 0),
        "strategy_active":         strategy_data.get("strategy_present", False),
        "governance_active":       governance_data.get("governance_present", False),
        "decision_queue_active":   governance_data.get("queue_governance_present", False),
        "repair_active":           repair_data.get("repair_plan_present", False),
    }

    result = verify_readiness_rule(claimed, evidence)
    result["claim_class"]   = "readiness"
    result["claim_key"]     = "readiness"
    result["claimed_value"] = claimed
    return [result]


def verify_posture_claims(
    self_awareness: dict[str, Any],
    strategy_data: dict[str, Any],
    governance_data: dict[str, Any],
    campaign_data: dict[str, Any],
    repair_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Verify posture claims from AG-47."""
    posture = self_awareness.get("posture", {}) or self_awareness.get("latest", {}).get("posture", {})
    results: list[dict[str, Any]] = []

    # Build flat evidence dict
    evidence = {
        "operator_action_required": governance_data.get("operator_action_required", False),
        "campaign_present":         campaign_data.get("campaign_present", False),
        "repair_execution_available": repair_data.get("repair_execution_available", False),
        "repair_plan_present":      repair_data.get("repair_plan_present", False),
        "queue_governance_present": governance_data.get("queue_governance_present", False),
        "strategy_present":         strategy_data.get("strategy_present", False),
        "outcome_intel_present":    campaign_data.get("outcome_intel_present", False),
    }

    # Verify operating_mode separately (compare string values)
    claimed_mode   = posture.get("operating_mode")
    observed_mode  = strategy_data.get("operating_mode")
    if claimed_mode is None:
        mode_verdict = "UNSUPPORTED"
        mode_reason  = "operating_mode not present in posture claim"
    elif observed_mode is None:
        mode_verdict = "UNSUPPORTED"
        mode_reason  = "operating_mode not found in strategy state"
    elif claimed_mode == observed_mode:
        mode_verdict = "VERIFIED"
        mode_reason  = f"claimed={claimed_mode!r} matches observed={observed_mode!r}"
    else:
        mode_verdict = "INCONSISTENT"
        mode_reason  = f"claimed={claimed_mode!r} != observed={observed_mode!r}"

    results.append({
        "claim_class":    "posture",
        "claim_key":      "operating_mode",
        "claimed_value":  claimed_mode,
        "observed_value": observed_mode,
        "verdict":        mode_verdict,
        "reason":         mode_reason,
        "evidence_refs":  ["runtime_operating_mode.json"],
    })

    # Verify each posture class dimension
    posture_dims = [
        ("governance_posture", posture.get("governance_posture")),
        ("repair_posture",     posture.get("repair_posture")),
        ("campaign_posture",   posture.get("campaign_posture")),
        ("decision_posture",   posture.get("decision_posture")),
        ("strategy_posture",   posture.get("strategy_posture")),
    ]

    for dim_key, claimed_class in posture_dims:
        if claimed_class is None:
            results.append({
                "claim_class": "posture",
                "claim_key":   dim_key,
                "claimed_value": None,
                "verdict":     "UNSUPPORTED",
                "reason":      f"no {dim_key} claim found",
                "evidence_refs": [],
            })
            continue
        result = verify_posture_rule(dim_key, claimed_class, evidence)
        result["claim_class"] = "posture"
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_claim_verification_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the full AG-48 claim verification report."""
    rt = _rt(runtime_root)

    self_awareness  = load_self_awareness(rt)
    capability_data = load_capability_envelope(rt)
    strategy_data   = load_runtime_strategy(rt)
    governance_data = load_governance_state(rt)
    campaign_data   = load_campaign_state(rt)
    repair_data     = load_repair_state(rt)

    identity_results  = verify_identity_claims(self_awareness, capability_data)
    readiness_results = verify_readiness_claims(
        self_awareness, capability_data, strategy_data, governance_data, repair_data
    )
    posture_results   = verify_posture_claims(
        self_awareness, strategy_data, governance_data, campaign_data, repair_data
    )

    all_results = identity_results + readiness_results + posture_results

    # Stats
    verdict_counts: dict[str, int] = {}
    for r in all_results:
        v = r.get("verdict", "INCONCLUSIVE")
        verdict_counts[v] = verdict_counts.get(v, 0) + 1

    verified_count     = verdict_counts.get("VERIFIED", 0)
    inconsistent_count = verdict_counts.get("INCONSISTENT", 0)
    unsupported_count  = verdict_counts.get("UNSUPPORTED", 0)

    mismatches = [r for r in all_results if r.get("verdict") in ("INCONSISTENT", "UNSUPPORTED")]
    top_issue  = mismatches[0].get("claim_key") if mismatches else None

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":                ts,
        "run_id":            str(uuid.uuid4()),
        "self_awareness_present": self_awareness["present"],
        "identity_results":  identity_results,
        "readiness_results": readiness_results,
        "posture_results":   posture_results,
        "all_results":       all_results,
        "verdict_counts":    verdict_counts,
        "verified_count":    verified_count,
        "inconsistent_count": inconsistent_count,
        "unsupported_count": unsupported_count,
        "total_claims":      len(all_results),
        "mismatches":        mismatches,
        "top_issue":         top_issue,
        "evidence_refs": [
            "runtime_self_awareness_latest.json",
            "runtime_capabilities.jsonl",
            "runtime_strategy_latest.json",
            "runtime_operating_mode.json",
            "drift_finding_status.json",
            "decision_queue_governance_latest.json",
        ],
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_claim_verification(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist AG-48 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_claim_verification_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    latest_path = state_dir / "runtime_claim_verification_latest.json"
    _atomic_write(latest_path, report)

    # 3. Slim verdicts summary (atomic)
    verdicts = {
        "ts":                report["ts"],
        "run_id":            report["run_id"],
        "verified_count":    report["verified_count"],
        "inconsistent_count": report["inconsistent_count"],
        "unsupported_count": report["unsupported_count"],
        "total_claims":      report["total_claims"],
        "top_issue":         report["top_issue"],
        "verdicts":          [
            {"claim_key": r.get("claim_key"), "verdict": r.get("verdict"),
             "claim_class": r.get("claim_class")}
            for r in report["all_results"]
        ],
    }
    verdicts_path = state_dir / "runtime_claim_verdicts.json"
    _atomic_write(verdicts_path, verdicts)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_claim_verification(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-48 claim verification and persist outputs."""
    try:
        report = build_claim_verification_report(runtime_root)
        store_claim_verification(report, runtime_root)
        return {
            "ok":                True,
            "verified_count":    report["verified_count"],
            "inconsistent_count": report["inconsistent_count"],
            "unsupported_count": report["unsupported_count"],
            "total_claims":      report["total_claims"],
            "top_issue":         report["top_issue"],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
