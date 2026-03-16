"""AG-47: Runtime Self-Awareness System.

Synthesizes active capabilities, runtime state, governance posture, repair
posture, and supervisory posture into a single self-describing runtime truth
surface.

Descriptive-only — no governance mutation, no campaign mutation, no repair
execution, no baseline mutation, no capability auto-activation.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from runtime.self_awareness_policy import (
    classify_governance_posture,
    classify_readiness,
    classify_repair_posture,
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

def load_capability_envelope(runtime_root: str | None = None) -> dict[str, Any]:
    """Load capability envelope from AG-46 outputs."""
    rt = _rt(runtime_root)
    try:
        from runtime.capability_registry import list_active_capabilities, registry_summary
        active = list_active_capabilities(rt)
        summary = registry_summary(rt)
    except Exception:
        active = []
        summary = {"total_registered": 0, "active_count": 0, "inactive_count": 0,
                   "active": [], "inactive": [], "all": []}

    return {
        "active_capabilities": active,
        "active_count": len(active),
        "summary": summary,
    }


def load_runtime_strategy(runtime_root: str | None = None) -> dict[str, Any]:
    """Load runtime strategy from AG-42 outputs."""
    rt = _rt(runtime_root)
    strategy = _read_json(Path(rt) / "state" / "runtime_strategy_latest.json") or {}
    mode_data = _read_json(Path(rt) / "state" / "runtime_operating_mode.json") or {}
    return {
        "operating_mode": (
            mode_data.get("operating_mode")
            or strategy.get("operating_mode")
        ),
        "confidence": mode_data.get("confidence", 0.0),
        "key_risks": strategy.get("key_risks", []),
        "recommendations": strategy.get("recommendations", []),
        "strategy_present": bool(strategy),
    }


def load_decision_queue_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load decision queue state from AG-43/AG-44 outputs."""
    rt = _rt(runtime_root)
    queue_latest  = _read_json(Path(rt) / "state" / "decision_queue_governance_latest.json") or {}
    decision_latest = _read_json(Path(rt) / "state" / "operator_decision_latest.json") or {}
    return {
        "queue_governance_present": bool(queue_latest),
        "decision_assist_present":  bool(decision_latest),
        "open_count":     queue_latest.get("open_count", 0),
        "urgent_count":   queue_latest.get("urgent_count", 0),
        "pending_decisions": decision_latest.get("pending_decisions", 0),
        "operator_action_required": (
            queue_latest.get("operator_action_required")
            or decision_latest.get("operator_action_required")
            or False
        ),
    }


def load_governance_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load governance state from AG-31/AG-32 outputs."""
    rt = _rt(runtime_root)
    findings = _read_json(Path(rt) / "state" / "drift_finding_status.json") or {}
    audit    = _read_json(Path(rt) / "state" / "runtime_self_audit.json") or {}
    gov_log  = _read_jsonl(Path(rt) / "state" / "drift_governance_log.jsonl")
    return {
        "governance_present":    bool(findings or audit),
        "findings_count":        len(findings),
        "audit_present":         bool(audit),
        "governance_log_entries": len(gov_log),
    }


def load_campaign_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load campaign state from AG-34/AG-40/AG-41 outputs."""
    rt = _rt(runtime_root)
    campaign = _read_json(Path(rt) / "state" / "repair_campaign_latest.json") or {}
    wave     = _read_json(Path(rt) / "state" / "repair_wave_latest.json") or {}
    outcome  = _read_json(Path(rt) / "state" / "repair_campaign_outcome_latest.json") or {}
    return {
        "campaign_present": bool(campaign or wave),
        "outcome_intel_present": bool(outcome),
        "wave_schedule_present": bool(
            _read_json(Path(rt) / "state" / "repair_wave_schedule.json")
        ),
    }


def load_repair_posture(runtime_root: str | None = None) -> dict[str, Any]:
    """Load repair posture from AG-33/AG-35/AG-38 outputs."""
    rt = _rt(runtime_root)
    priority  = _read_json(Path(rt) / "state" / "repair_priority_latest.json") or {}
    plan      = _read_json(Path(rt) / "state" / "drift_repair_plan_latest.json") or {}
    recon     = _read_json(Path(rt) / "state" / "repair_reconciliation_latest.json") or {}
    exec_log  = _read_jsonl(Path(rt) / "state" / "drift_repair_execution_log.jsonl")
    return {
        "repair_plan_present":        bool(plan),
        "repair_priority_present":    bool(priority),
        "repair_reconciliation_present": bool(recon),
        "repair_execution_available": bool(exec_log or plan),
        "execution_count":            len(exec_log),
    }


# ---------------------------------------------------------------------------
# Derivation functions
# ---------------------------------------------------------------------------

def derive_runtime_identity(
    capability_data: dict[str, Any],
    strategy_data: dict[str, Any],
) -> dict[str, Any]:
    """Produce a deterministic self-description of what this runtime is."""
    return {
        "system_identity": "Supervised Agentic Runtime Platform",
        "runtime_role": "governed execution + supervised repair + advisory intelligence",
        "active_capability_count": capability_data.get("active_count", 0),
        "active_capabilities": capability_data.get("active_capabilities", []),
        "operating_mode": strategy_data.get("operating_mode") or "UNKNOWN",
    }


def derive_runtime_readiness(
    capability_data: dict[str, Any],
    strategy_data: dict[str, Any],
    decision_data: dict[str, Any],
    governance_data: dict[str, Any],
    repair_data: dict[str, Any],
) -> dict[str, Any]:
    """Derive readiness class and supporting evidence."""
    inputs = {
        "active_capability_count": capability_data.get("active_count", 0),
        "strategy_active":         strategy_data.get("strategy_present", False),
        "governance_active":       governance_data.get("governance_present", False),
        "decision_queue_active":   decision_data.get("queue_governance_present", False),
        "repair_active":           repair_data.get("repair_plan_present", False),
        "operating_mode":          strategy_data.get("operating_mode", ""),
    }
    readiness = classify_readiness(inputs)

    reasons: list[str] = []
    if capability_data.get("active_count", 0) > 0:
        reasons.append(f"capability envelope populated ({capability_data['active_count']} active)")
    if strategy_data.get("strategy_present"):
        reasons.append("strategy layer active")
    if governance_data.get("governance_present"):
        reasons.append("governance state present")
    if decision_data.get("queue_governance_present"):
        reasons.append("decision governance active")
    if repair_data.get("repair_plan_present"):
        reasons.append("repair planning active")
    if not reasons:
        reasons.append("minimal runtime state detected")

    # Derive a simple confidence based on signals present
    signals = [
        capability_data.get("active_count", 0) > 0,
        strategy_data.get("strategy_present", False),
        governance_data.get("governance_present", False),
        decision_data.get("queue_governance_present", False),
        repair_data.get("repair_plan_present", False),
    ]
    confidence = round(sum(signals) / len(signals), 2)

    return {
        "readiness": readiness,
        "confidence": confidence,
        "reasons": reasons,
    }


def derive_runtime_posture(
    strategy_data: dict[str, Any],
    governance_data: dict[str, Any],
    repair_data: dict[str, Any],
    campaign_data: dict[str, Any],
    decision_data: dict[str, Any],
) -> dict[str, Any]:
    """Derive current runtime posture across all layers."""
    gov_posture = classify_governance_posture({
        "governance_findings_count": governance_data.get("findings_count", 0),
        "operator_action_required":  decision_data.get("operator_action_required", False),
    })

    repair_posture = classify_repair_posture({
        "repair_plan_present":        repair_data.get("repair_plan_present", False),
        "repair_execution_available": repair_data.get("repair_execution_available", False),
    })

    campaign_posture = (
        "CAMPAIGN_CONTROLLED" if campaign_data.get("campaign_present") else
        "CAMPAIGN_ADVISORY"   if campaign_data.get("outcome_intel_present") else
        "CAMPAIGN_ABSENT"
    )

    decision_posture = (
        "QUEUE_GOVERNED"  if decision_data.get("queue_governance_present") else
        "DECISION_ASSIST" if decision_data.get("decision_assist_present") else
        "DECISION_ABSENT"
    )

    strategy_posture = (
        "STRATEGY_ADVISORY" if strategy_data.get("strategy_present") else
        "STRATEGY_ABSENT"
    )

    return {
        "operating_mode":     strategy_data.get("operating_mode") or "UNKNOWN",
        "governance_posture": gov_posture,
        "repair_posture":     repair_posture,
        "campaign_posture":   campaign_posture,
        "decision_posture":   decision_posture,
        "strategy_posture":   strategy_posture,
    }


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_self_awareness_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the full AG-47 runtime self-awareness report."""
    rt = _rt(runtime_root)

    capability_data = load_capability_envelope(rt)
    strategy_data   = load_runtime_strategy(rt)
    decision_data   = load_decision_queue_state(rt)
    governance_data = load_governance_state(rt)
    campaign_data   = load_campaign_state(rt)
    repair_data     = load_repair_posture(rt)

    identity  = derive_runtime_identity(capability_data, strategy_data)
    readiness = derive_runtime_readiness(
        capability_data, strategy_data, decision_data, governance_data, repair_data
    )
    posture   = derive_runtime_posture(
        strategy_data, governance_data, repair_data, campaign_data, decision_data
    )

    # Identify critical gaps
    gaps: list[str] = []
    if capability_data.get("active_count", 0) == 0:
        gaps.append("capability envelope empty — no active capabilities registered")
    if not strategy_data.get("strategy_present"):
        gaps.append("runtime strategy layer not active (AG-42 not run)")
    if not governance_data.get("governance_present"):
        gaps.append("governance state absent (AG-31/AG-32 not run)")
    if not decision_data.get("queue_governance_present"):
        gaps.append("decision queue governance not active (AG-44 not run)")

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":              ts,
        "run_id":          str(uuid.uuid4()),
        "identity":        identity,
        "readiness":       readiness,
        "posture":         posture,
        "critical_gaps":   gaps,
        "evidence_refs": [
            "runtime_capabilities.jsonl",
            "runtime_strategy_latest.json",
            "runtime_operating_mode.json",
            "decision_queue_governance_latest.json",
            "operator_decision_latest.json",
            "drift_finding_status.json",
            "repair_wave_schedule.json",
        ],
        "operator_action_required": False,  # descriptive only — no action implied
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_self_awareness(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist AG-47 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_self_awareness_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    latest_path = state_dir / "runtime_self_awareness_latest.json"
    _atomic_write(latest_path, report)

    # 3. Slim readiness summary (atomic)
    readiness_summary = {
        "ts":       report["ts"],
        "run_id":   report["run_id"],
        "readiness": report["readiness"]["readiness"],
        "confidence": report["readiness"]["confidence"],
        "reasons":   report["readiness"]["reasons"],
        "operating_mode": report["posture"]["operating_mode"],
        "critical_gaps": report["critical_gaps"],
    }
    readiness_path = state_dir / "runtime_readiness.json"
    _atomic_write(readiness_path, readiness_summary)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_self_awareness(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-47 self-awareness synthesis and persist outputs."""
    try:
        report = build_self_awareness_report(runtime_root)
        store_self_awareness(report, runtime_root)
        return {
            "ok":              True,
            "readiness":       report["readiness"]["readiness"],
            "operating_mode":  report["posture"]["operating_mode"],
            "active_capabilities": report["identity"]["active_capability_count"],
            "critical_gaps":   len(report["critical_gaps"]),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
