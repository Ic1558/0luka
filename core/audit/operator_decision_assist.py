"""AG-43: Operator Decision Assist Layer.

Aggregates context from AG-37/38/39/41/42 to build operator-ready decision
packages — structured summaries of options, risks, rationale, and evidence.

Invariants:
  - assist-only: never mutates governance state, campaign state, baseline, or repairs
  - no automatic approval or rejection — all decisions remain with the operator
  - deterministic given the same input state
  - every package is explainable and evidence-backed

Runtime outputs:
  $LUKA_RUNTIME_ROOT/state/operator_decision_packages.jsonl — append-only
  $LUKA_RUNTIME_ROOT/state/operator_decision_latest.json   — atomic overwrite
  $LUKA_RUNTIME_ROOT/state/operator_decision_queue.json    — atomic overwrite

Public API:
  run_operator_decision_assist(runtime_root=None) -> dict
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from core.audit.decision_package_policy import (
    DECISION_TYPES,
    RECOMMENDATION_TO_DECISION_TYPE,
    classify_decision_priority,
    recommendation_to_decision_type,
    valid_decision_type,
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _state_dir(runtime_root: str | None = None) -> Path:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT is required (fail-closed).")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl(path: Path, limit: int = 500) -> list[dict[str, Any]]:
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


def _new_decision_id() -> str:
    return "decision-" + uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Source readers
# ---------------------------------------------------------------------------

def load_runtime_strategy(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-42 supervisory strategy state."""
    state_d = _state_dir(runtime_root)
    latest  = _read_json(state_d / "runtime_strategy_latest.json") or {}
    mode    = _read_json(state_d / "runtime_operating_mode.json") or {}
    return {
        "operating_mode":       str(mode.get("operating_mode") or latest.get("operating_mode") or "REPAIR_FOCUSED"),
        "mode_confidence":      float(mode.get("confidence", latest.get("mode_confidence", 0.5))),
        "mode_reasons":         mode.get("reasons") or latest.get("mode_reasons") or [],
        "key_risks":            mode.get("key_risks") or latest.get("key_risks") or [],
        "recommendations":      latest.get("recommendations") or [],
        "recommendation_count": int(latest.get("recommendation_count", 0)),
    }


def load_drift_governance_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-32 drift governance snapshot."""
    state_d = _state_dir(runtime_root)
    status_map: dict[str, Any] = _read_json(state_d / "drift_finding_status.json") or {}
    escalated = [fid for fid, rec in status_map.items()
                 if rec.get("status") in ("ESCALATED", "ESCALATED_AGAIN")]
    open_fids = [fid for fid, rec in status_map.items()
                 if rec.get("status") == "OPEN"]
    return {
        "total_findings":  len(status_map),
        "escalated_count": len(escalated),
        "open_count":      len(open_fids),
        "escalated_ids":   escalated[:10],  # cap for package readability
    }


def load_repair_priority(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-38 repair priority state."""
    state_d = _state_dir(runtime_root)
    latest  = _read_json(state_d / "repair_priority_latest.json") or {}
    queue_d = _read_json(state_d / "repair_priority_queue.json") or {}
    queue   = queue_d.get("queue", [])
    return {
        "total_items":   int(latest.get("total_items", len(queue))),
        "p1_count":      int(latest.get("p1_count", 0)),
        "p2_count":      int(latest.get("p2_count", 0)),
        "top_priority":  latest.get("top_priority"),
        "queue":         queue[:20],  # cap
    }


def load_campaign_outcomes(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-41 campaign outcome intelligence."""
    state_d = _state_dir(runtime_root)
    latest   = _read_json(state_d / "repair_campaign_outcome_latest.json") or {}
    patterns = (_read_json(state_d / "campaign_pattern_registry.json") or {}).get("patterns", [])
    return {
        "active_regressions":     len(latest.get("regressions", [])),
        "overall_recommendation": str(latest.get("overall_recommendation") or "REVIEW_PATTERN"),
        "high_risk_patterns":     sum(1 for p in patterns if p.get("recommendation") == "HIGH_RISK_PATTERN"),
        "patterns":               patterns,
    }


def load_repair_wave_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-39 wave schedule state."""
    state_d = _state_dir(runtime_root)
    schedule = _read_json(state_d / "repair_wave_schedule.json") or {}
    waves    = schedule.get("waves", [])
    proposed = [w for w in waves if w.get("status") == "PROPOSED"]
    return {
        "total_waves":    len(waves),
        "proposed_waves": len(proposed),
        "proposed":       proposed[:5],  # top 5 for packages
        "deferred_items": schedule.get("deferred_items", 0),
    }


# ---------------------------------------------------------------------------
# Decision candidate builder
# ---------------------------------------------------------------------------

def build_decision_candidates(
    strategy: dict[str, Any],
    governance: dict[str, Any],
    priority: dict[str, Any],
    outcomes: dict[str, Any],
    wave_state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Construct decision candidates from aggregated runtime context.

    Each candidate represents one pending operator decision.
    Returns list sorted by priority (CRITICAL first).
    """
    candidates: list[dict[str, Any]] = []
    mode       = strategy.get("operating_mode", "REPAIR_FOCUSED")
    regressions = outcomes.get("active_regressions", 0)
    high_risk   = outcomes.get("high_risk_patterns", 0)
    p1_count    = priority.get("p1_count", 0)

    # 1. Wave approval candidates (one per PROPOSED wave)
    for wave in wave_state.get("proposed", []):
        wave_id = wave.get("wave_id", "")
        p_classes = wave.get("priority_classes_present", [])
        is_p1_wave = "P1" in p_classes
        dtype = "APPROVE_REPAIR_WAVE" if mode not in ("STABILIZE", "HIGH_RISK_HOLD") else "DEFER_REPAIR_WAVE"
        prio  = classify_decision_priority({
            "operating_mode":    mode,
            "p1_count":          p1_count,
            "active_regressions": regressions,
            "high_risk_patterns": high_risk,
            "decision_type":     dtype,
        })
        candidates.append({
            "decision_id":            _new_decision_id(),
            "decision_type":          dtype,
            "target_ref":             wave_id,
            "target_class":           "repair_wave",
            "priority":               prio,
            "operator_action_required": True,
            "context": {
                "wave_priority_classes": p_classes,
                "item_count":            wave.get("item_count", 0),
            },
        })

    # 2. Pause new campaigns if strategy recommends it
    if any(r.get("recommendation") == "PAUSE_NEW_CAMPAIGNS"
           for r in strategy.get("recommendations", [])):
        prio = classify_decision_priority({
            "operating_mode":    mode,
            "active_regressions": regressions,
            "decision_type":     "PAUSE_NEW_CAMPAIGNS",
        })
        candidates.append({
            "decision_id":            _new_decision_id(),
            "decision_type":          "PAUSE_NEW_CAMPAIGNS",
            "target_ref":             "campaign-scheduler",
            "target_class":           "campaign_policy",
            "priority":               prio,
            "operator_action_required": True,
            "context": {"trigger": "supervisory_strategy_recommendation"},
        })

    # 3. Escalate high-risk components
    if high_risk >= 1 or any(r.get("recommendation") == "ISOLATE_HIGH_RISK_COMPONENTS"
                              for r in strategy.get("recommendations", [])):
        candidates.append({
            "decision_id":            _new_decision_id(),
            "decision_type":          "ESCALATE_HIGH_RISK_COMPONENT",
            "target_ref":             "high-risk-component-set",
            "target_class":           "component_group",
            "priority":               "HIGH",
            "operator_action_required": True,
            "context": {"high_risk_pattern_count": high_risk},
        })

    # 4. Governance review if stability is critical or governance findings pending
    if governance.get("escalated_count", 0) >= 3 or mode in ("STABILIZE", "GOVERNANCE_REVIEW"):
        candidates.append({
            "decision_id":            _new_decision_id(),
            "decision_type":          "REQUIRE_GOVERNANCE_REVIEW",
            "target_ref":             "drift-governance-state",
            "target_class":           "governance_lifecycle",
            "priority":               "CRITICAL" if mode == "STABILIZE" else "HIGH",
            "operator_action_required": True,
            "context": {
                "escalated_findings": governance.get("escalated_count", 0),
                "operating_mode":     mode,
            },
        })

    # 5. Pattern reuse review if strategy recommends it
    if any(r.get("recommendation") in ("REVIEW_PATTERN_BEFORE_REUSE", "REVIEW_FAILED_CAMPAIGNS")
           for r in strategy.get("recommendations", [])):
        candidates.append({
            "decision_id":            _new_decision_id(),
            "decision_type":          "REVIEW_PATTERN_REUSE",
            "target_ref":             "campaign-pattern-registry",
            "target_class":           "campaign_patterns",
            "priority":               "MEDIUM",
            "operator_action_required": True,
            "context": {"overall_campaign_recommendation": outcomes.get("overall_recommendation")},
        })

    # Sort by priority
    prio_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    candidates.sort(key=lambda c: prio_order.get(c["priority"], 99))
    return candidates


# ---------------------------------------------------------------------------
# Decision package generator
# ---------------------------------------------------------------------------

def generate_decision_package(
    candidate: dict[str, Any],
    strategy: dict[str, Any],
    priority_data: dict[str, Any],
) -> dict[str, Any]:
    """Produce a full deterministic decision package from a candidate.

    Package contains: summary, rationale, risks, evidence_refs, alternatives,
    recommended_action — all advisory, all operator-facing.
    """
    dtype      = candidate.get("decision_type", "")
    target_ref = candidate.get("target_ref", "")
    context    = candidate.get("context", {})
    mode       = strategy.get("operating_mode", "REPAIR_FOCUSED")
    dtype_meta = DECISION_TYPES.get(dtype, {})
    alternatives = dtype_meta.get("alternatives", [])

    # Build rationale from available signals
    rationale: list[str] = []
    risks:     list[str] = []
    evidence:  list[str] = []

    if dtype == "APPROVE_REPAIR_WAVE":
        p_classes = context.get("wave_priority_classes", [])
        item_count = context.get("item_count", 0)
        rationale.append(f"wave_priority_classes={p_classes}")
        rationale.append(f"item_count={item_count}")
        rationale.append(f"operating_mode={mode}")
        if "P1" in p_classes:
            rationale.append("contains P1 findings — high governance urgency")
        risks.append("shared component sensitivity if wave overlaps other active repairs")
        evidence.extend(["repair_priority_queue.json", "runtime_strategy_latest.json",
                          "repair_wave_schedule.json"])

    elif dtype == "DEFER_REPAIR_WAVE":
        rationale.append(f"operating_mode={mode} — wave execution not recommended")
        rationale.append("defer until stability improves or regressions resolved")
        risks.append("deferring P1 items may increase governance debt")
        evidence.extend(["runtime_strategy_latest.json", "repair_wave_schedule.json"])

    elif dtype == "PAUSE_NEW_CAMPAIGNS":
        rationale.append("supervisory strategy recommends pausing campaign creation")
        rationale.append(f"operating_mode={mode}")
        risks.append("pausing campaigns extends repair backlog")
        evidence.extend(["runtime_strategy_latest.json", "repair_campaign_outcome_latest.json"])

    elif dtype == "ESCALATE_HIGH_RISK_COMPONENT":
        hrc = context.get("high_risk_pattern_count", 0)
        rationale.append(f"high_risk_campaign_patterns={hrc}")
        rationale.append("component associated with regression-prone campaign pattern")
        risks.append("isolation may delay other repair waves sharing this component")
        evidence.extend(["campaign_pattern_registry.json", "runtime_strategy_latest.json"])

    elif dtype == "REQUIRE_GOVERNANCE_REVIEW":
        esc = context.get("escalated_findings", 0)
        rationale.append(f"escalated_findings={esc}")
        rationale.append(f"operating_mode={mode} — governance attention required")
        risks.append("repair activity without governance review may worsen drift")
        evidence.extend(["drift_finding_status.json", "runtime_strategy_latest.json"])

    elif dtype == "REVIEW_PATTERN_REUSE":
        rationale.append("campaign pattern has mixed or negative outcome history")
        rationale.append(f"overall_campaign_recommendation={context.get('overall_campaign_recommendation')}")
        risks.append("reusing a regression-prone pattern may cause new campaign failures")
        evidence.extend(["campaign_pattern_registry.json", "repair_campaign_outcome_latest.json"])

    elif dtype in ("ACCEPT_BASELINE_PROPOSAL", "REJECT_BASELINE_PROPOSAL"):
        rationale.append("AG-36 baseline realignment proposal awaiting operator decision")
        evidence.extend(["baseline_realign_latest.json"])
        risks.append("accepting incorrect proposals may misalign audit baseline")

    else:
        rationale.append(f"decision_type={dtype}")
        evidence.append("runtime_strategy_latest.json")

    # Summary
    summary = dtype_meta.get("description", f"Operator decision required: {dtype}")

    return {
        "ts":                     _now(),
        "decision_id":            candidate["decision_id"],
        "decision_type":          dtype,
        "target_ref":             target_ref,
        "target_class":           candidate.get("target_class", ""),
        "operating_mode":         mode,
        "summary":                summary,
        "rationale":              rationale,
        "risks":                  risks,
        "evidence_refs":          evidence,
        "alternatives":           alternatives,
        "recommended_action":     dtype,
        "priority":               candidate.get("priority", "MEDIUM"),
        "operator_action_required": True,
        "status":                 "PROPOSED",
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_decision_assist_report(
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Build a full AG-43 operator decision assist report."""
    strategy   = load_runtime_strategy(runtime_root)
    governance = load_drift_governance_state(runtime_root)
    priority   = load_repair_priority(runtime_root)
    outcomes   = load_campaign_outcomes(runtime_root)
    wave_state = load_repair_wave_state(runtime_root)

    candidates = build_decision_candidates(strategy, governance, priority, outcomes, wave_state)
    packages   = [generate_decision_package(c, strategy, priority) for c in candidates]

    # Distribution by type
    type_dist: dict[str, int] = {}
    for pkg in packages:
        dt = pkg["decision_type"]
        type_dist[dt] = type_dist.get(dt, 0) + 1

    # Top decision
    top = packages[0] if packages else None

    # Urgent vs deferred
    urgent   = [p for p in packages if p["priority"] in ("CRITICAL", "HIGH")]
    deferred = [p for p in packages if p["priority"] in ("MEDIUM", "LOW")]

    return {
        "ts":                _now(),
        "run_id":            "decision-assist-" + uuid.uuid4().hex[:8],
        "operating_mode":    strategy["operating_mode"],
        "pending_decisions": len(packages),
        "urgent_count":      len(urgent),
        "deferred_count":    len(deferred),
        "packages":          packages,
        "type_distribution": type_dist,
        "top_decision": {
            "decision_id":    top["decision_id"],
            "decision_type":  top["decision_type"],
            "priority":       top["priority"],
            "summary":        top["summary"],
        } if top else None,
        "key_risks":          strategy.get("key_risks", []),
        "operator_action_required": True,
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_decision_assist(
    report: dict[str, Any],
    runtime_root: str | None = None,
) -> None:
    """Write AG-43 outputs: append log, atomic latest, atomic queue."""
    state_d = _state_dir(runtime_root)

    # 1. Append to packages log
    log_path = state_d / "operator_decision_packages.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts":            report["ts"],
            "run_id":        report["run_id"],
            "pending":       report["pending_decisions"],
            "operating_mode": report["operating_mode"],
        }) + "\n")

    # 2. Atomic latest (full report)
    _atomic_write(state_d / "operator_decision_latest.json", report)

    # 3. Atomic queue (packages only, for quick polling)
    _atomic_write(state_d / "operator_decision_queue.json", {
        "ts":             report["ts"],
        "run_id":         report["run_id"],
        "operating_mode": report["operating_mode"],
        "pending":        report["pending_decisions"],
        "urgent_count":   report["urgent_count"],
        "packages":       report["packages"],
        "type_distribution": report["type_distribution"],
    })


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_operator_decision_assist(runtime_root: str | None = None) -> dict[str, Any]:
    """Run the full AG-43 operator decision assist analysis.

    Steps:
      1. Load strategy, governance, priority, outcomes, wave state
      2. Build decision candidates
      3. Generate decision packages
      4. Build report
      5. Store outputs
      6. Return summary

    Never modifies governance state, campaign state, baseline, or repair artifacts.
    All packages are advisory. Operator remains final authority.
    """
    report = build_decision_assist_report(runtime_root)

    try:
        store_decision_assist(report, runtime_root)
    except Exception as exc:
        report["storage_error"] = str(exc)

    return {
        "ok":                True,
        "run_id":            report["run_id"],
        "operating_mode":    report["operating_mode"],
        "pending_decisions": report["pending_decisions"],
        "urgent_count":      report["urgent_count"],
        "top_decision_type": report["top_decision"]["decision_type"] if report["top_decision"] else None,
    }
