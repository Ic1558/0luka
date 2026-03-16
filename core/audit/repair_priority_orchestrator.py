"""AG-38: Repair Priority Orchestration Layer.

Reads drift findings, repair plans, execution history, and AG-37 intelligence
to produce a deterministic, ranked repair priority queue.

Invariants:
  - ordering-only: never executes repairs, approves plans, or closes findings
  - never modifies governance state or baseline
  - all queue items are advisory; operator remains final authority
  - queue is deterministic given the same input state

Runtime outputs:
  $LUKA_RUNTIME_ROOT/state/repair_priority_queue.json   — atomic overwrite
  $LUKA_RUNTIME_ROOT/state/repair_priority_log.jsonl    — append-only
  $LUKA_RUNTIME_ROOT/state/repair_priority_latest.json  — atomic overwrite

Public API:
  run_repair_priority_orchestration(runtime_root=None) -> dict
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from core.audit.priority_policy import (
    FAILED_REPAIR_URGENCY,
    PATTERN_BONUS,
    SEVERITY_BONUS,
    STATUS_BASE_SCORE,
    classify_priority,
    priority_reason_codes,
)
from core.audit.drift_pattern_registry import classify_drift_to_pattern


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _state_dir(runtime_root: str | None = None) -> Path:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT is required (fail-closed).")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_jsonl(path: Path, limit: int = 2000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    results = []
    try:
        for line in path.read_text(encoding="utf-8").strip().splitlines()[-limit:]:
            try:
                results.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        pass
    return results


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Source readers
# ---------------------------------------------------------------------------

def load_open_governed_findings(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load findings requiring active operator attention from AG-32 governance state.

    Includes: ESCALATED, ESCALATED_AGAIN, OPEN, ACCEPTED (not yet promoted).
    Excludes: RESOLVED, DISMISSED.
    """
    state_d = _state_dir(runtime_root)
    status_path = state_d / "drift_finding_status.json"
    if not status_path.exists():
        return []
    try:
        status_map: dict[str, dict[str, Any]] = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    actionable_statuses = {"ESCALATED", "ESCALATED_AGAIN", "OPEN", "ACCEPTED"}
    actionable_ids = {
        fid for fid, rec in status_map.items()
        if rec.get("status") in actionable_statuses
    }
    if not actionable_ids:
        return []

    # Enrich with AG-31 drift evidence
    evidence: dict[str, dict[str, Any]] = {}
    findings_path = state_d / "drift_findings.jsonl"
    for rec in _read_jsonl(findings_path):
        fid = str(rec.get("id") or rec.get("finding_id") or "")
        if fid in actionable_ids:
            evidence[fid] = rec

    results = []
    for fid in actionable_ids:
        gov_rec = dict(status_map[fid])
        merged: dict[str, Any] = {**(evidence.get(fid, {})), **gov_rec}
        merged["finding_id"] = fid
        results.append(merged)
    return results


def load_repair_plans(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load AG-33 repair plans."""
    return _read_jsonl(_state_dir(runtime_root) / "drift_repair_plans.jsonl")


def load_repair_history(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load AG-34 execution log + AG-35 reconciliation log."""
    state_d = _state_dir(runtime_root)
    executions     = _read_jsonl(state_d / "drift_repair_execution_log.jsonl")
    reconciliations = _read_jsonl(state_d / "repair_reconciliation_log.jsonl")
    return executions + reconciliations


def load_drift_intelligence(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-37 intelligence artifacts."""
    state_d = _state_dir(runtime_root)
    result: dict[str, Any] = {}
    for filename in ("drift_intelligence_latest.json",
                     "runtime_stability_score.json",
                     "drift_pattern_registry.json"):
        path = state_d / filename
        if path.exists():
            try:
                result[filename] = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
    return result


# ---------------------------------------------------------------------------
# Derived indexes for scoring
# ---------------------------------------------------------------------------

def _build_hotspot_index(intelligence: dict[str, Any]) -> dict[str, int]:
    """Return {component: drift_count} from intelligence hotspot data."""
    report = intelligence.get("drift_intelligence_latest.json", {})
    hotspots = report.get("hotspot_components", [])
    return {h["component"]: h["drift_count"] for h in hotspots if "component" in h}


def _build_pattern_index(intelligence: dict[str, Any]) -> dict[str, list[str]]:
    """Return {pattern_class: [affected_components]} from pattern registry."""
    registry = intelligence.get("drift_pattern_registry.json", {})
    patterns = registry.get("patterns", [])
    index: dict[str, list[str]] = {}
    for p in patterns:
        cls = p.get("pattern_class", "")
        if cls:
            index[cls] = p.get("affected_components", [])
    return index


def _build_failed_repair_index(history: list[dict[str, Any]]) -> dict[str, int]:
    """Return {finding_id: failed_repair_count}."""
    counts: dict[str, int] = {}
    for rec in history:
        if rec.get("status") == "FAILED" or rec.get("verification_status") == "FAILED":
            fid = str(rec.get("finding_id") or "")
            if fid:
                counts[fid] = counts.get(fid, 0) + 1
    return counts


def _build_plan_index(plans: list[dict[str, Any]]) -> dict[str, str]:
    """Return {finding_id: plan_id} for the most recent plan per finding."""
    index: dict[str, str] = {}
    for p in plans:
        fid = str(p.get("finding_id") or "")
        pid = str(p.get("plan_id") or "")
        if fid and pid:
            index[fid] = pid  # last wins (JSONL is append-only so last is newest)
    return index


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_repair_priority(
    finding: dict[str, Any],
    hotspot_index: dict[str, int] | None = None,
    pattern_index: dict[str, list[str]] | None = None,
    failed_repair_index: dict[str, int] | None = None,
    stability_score: int = 100,
) -> dict[str, Any]:
    """Compute a deterministic priority score for a finding.

    Score components:
      - base: governance status
      - +severity bonus
      - +pattern class bonus (highest applicable pattern)
      - +hotspot bonus
      - +failed repair urgency
      - +stability impact bonus
      - +operator gate risk bonus

    Returns dict with: finding_id, priority_score, priority_class, reasons.
    """
    hotspot_index = hotspot_index or {}
    pattern_index = pattern_index or {}
    failed_repair_index = failed_repair_index or {}

    fid = str(finding.get("finding_id") or finding.get("id") or "unknown")
    status = str(finding.get("status") or "OPEN")
    severity = str(finding.get("severity") or "MEDIUM").upper()
    drift_type = str(finding.get("drift_type") or finding.get("drift_class") or "unknown")
    component = str(finding.get("component") or "")

    reasons: list[str] = []
    score = STATUS_BASE_SCORE.get(status, 20)

    # Severity bonus
    sev_bonus = SEVERITY_BONUS.get(severity, 0)
    score += sev_bonus
    if sev_bonus >= SEVERITY_BONUS["HIGH"]:
        reasons.append("high_severity")

    # Operator gate risk (highest priority trigger)
    if drift_type in ("operator_gate_regression", "operator_gate_missing"):
        score += 30
        reasons.append("operator_gate_risk")

    # Pattern class bonus — find highest applicable bonus
    pattern_cls = classify_drift_to_pattern(drift_type)
    if pattern_cls and pattern_cls in pattern_index:
        bonus = PATTERN_BONUS.get(pattern_cls, 0)
        score += bonus
        if bonus > 0:
            reasons.append("recurring_pattern")

    # Hotspot bonus
    hotspot_count = hotspot_index.get(component, 0)
    if hotspot_count >= 5:
        score += 15
        reasons.append("hotspot_component")
    elif hotspot_count >= 3:
        score += 8
        reasons.append("hotspot_component")

    # Failed repair urgency
    failed_count = failed_repair_index.get(fid, 0)
    urgency_bonus = FAILED_REPAIR_URGENCY.get(min(failed_count, 3), 15)
    score += urgency_bonus
    if urgency_bonus > 0:
        reasons.append("failed_repair_history")

    # Escalated status bonus
    if status in ("ESCALATED", "ESCALATED_AGAIN"):
        score += 10
        reasons.append("escalated_status")

    # Stability impact: if system is UNSTABLE/GOVERNANCE_RISK, all findings get a bump
    if stability_score < 40:
        score += 10
        reasons.append("stability_impact")
    elif stability_score < 60:
        score += 5

    # Clamp
    score = max(0, min(100, score))
    priority_class = classify_priority(score)

    return {
        "finding_id": fid,
        "priority_score": score,
        "priority_class": priority_class,
        "reasons": reasons,
        "drift_type": drift_type,
        "severity": severity,
        "gov_status": status,
        "component": component,
    }


# ---------------------------------------------------------------------------
# Queue builder
# ---------------------------------------------------------------------------

def build_priority_queue(
    findings: list[dict[str, Any]],
    plan_index: dict[str, str] | None = None,
    hotspot_index: dict[str, int] | None = None,
    pattern_index: dict[str, list[str]] | None = None,
    failed_repair_index: dict[str, int] | None = None,
    stability_score: int = 100,
) -> list[dict[str, Any]]:
    """Build a deterministic ranked repair priority queue.

    Returns items sorted by priority_score descending, with recommended_order assigned.
    """
    plan_index = plan_index or {}
    queue_items = []

    for finding in findings:
        scored = score_repair_priority(
            finding,
            hotspot_index=hotspot_index,
            pattern_index=pattern_index,
            failed_repair_index=failed_repair_index,
            stability_score=stability_score,
        )
        fid = scored["finding_id"]
        queue_items.append({
            **scored,
            "plan_id": plan_index.get(fid, ""),
        })

    # Sort by score desc, then finding_id asc for determinism
    queue_items.sort(key=lambda x: (-x["priority_score"], x["finding_id"]))

    for i, item in enumerate(queue_items, 1):
        item["recommended_order"] = i

    return queue_items


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_priority_queue(
    queue: list[dict[str, Any]],
    summary: dict[str, Any],
    runtime_root: str | None = None,
) -> None:
    """Write AG-38 outputs: queue JSON (atomic), append log, atomic latest."""
    state_d = _state_dir(runtime_root)

    # 1. Atomic queue snapshot
    _atomic_write(state_d / "repair_priority_queue.json", {
        "ts": _now(),
        "total": len(queue),
        "queue": queue,
    })

    # 2. Append to priority log
    log_path = state_d / "repair_priority_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")

    # 3. Atomic latest
    _atomic_write(state_d / "repair_priority_latest.json", summary)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_repair_priority_orchestration(runtime_root: str | None = None) -> dict[str, Any]:
    """Run the full AG-38 repair priority orchestration.

    Steps:
      1. Load open governed findings
      2. Load repair plans, history, intelligence
      3. Build scoring indexes
      4. Score and rank each finding
      5. Build priority queue
      6. Store outputs
      7. Return summary

    Never modifies governance state, baseline, findings, or repair artifacts.
    """
    findings    = load_open_governed_findings(runtime_root)
    plans       = load_repair_plans(runtime_root)
    history     = load_repair_history(runtime_root)
    intelligence = load_drift_intelligence(runtime_root)

    # Build indexes
    hotspot_index      = _build_hotspot_index(intelligence)
    pattern_index      = _build_pattern_index(intelligence)
    failed_repair_index = _build_failed_repair_index(history)
    plan_index         = _build_plan_index(plans)

    # Get current stability score
    score_data = intelligence.get("runtime_stability_score.json", {})
    stability_score = int(score_data.get("score", 100))

    # Build queue
    queue = build_priority_queue(
        findings,
        plan_index=plan_index,
        hotspot_index=hotspot_index,
        pattern_index=pattern_index,
        failed_repair_index=failed_repair_index,
        stability_score=stability_score,
    )

    # P1/P2 counts
    p1_count = sum(1 for item in queue if item["priority_class"] == "P1")
    p2_count = sum(1 for item in queue if item["priority_class"] == "P2")
    top = queue[0] if queue else None

    summary: dict[str, Any] = {
        "ts": _now(),
        "run_id": "priority-" + uuid.uuid4().hex[:8],
        "total_items": len(queue),
        "p1_count": p1_count,
        "p2_count": p2_count,
        "stability_score": stability_score,
        "top_priority": {
            "finding_id": top["finding_id"],
            "priority_class": top["priority_class"],
            "priority_score": top["priority_score"],
            "reasons": top["reasons"],
        } if top else None,
    }

    try:
        store_priority_queue(queue, summary, runtime_root)
    except Exception as exc:
        summary["storage_error"] = str(exc)

    return {
        "ok": True,
        "run_id": summary["run_id"],
        "total_items": len(queue),
        "p1_count": p1_count,
        "p2_count": p2_count,
        "top_priority": summary["top_priority"],
    }
