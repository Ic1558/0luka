"""AG-42: Supervisory Runtime Strategy Layer.

Aggregates intelligence from AG-37 (drift), AG-38 (priority), AG-39 (waves),
AG-40 (campaigns), and AG-41 (campaign outcomes) to produce a supervisory
strategy recommendation: operating mode, key risks, and advisory posture.

Invariants:
  - advisory-only: never mutates campaign state, governance state, baseline, or repairs
  - no auto-mode switching: operating mode is a recommendation, not an enforcement
  - deterministic given the same input state
  - operator remains final authority

Runtime outputs:
  $LUKA_RUNTIME_ROOT/state/runtime_strategy_latest.json  — atomic overwrite
  $LUKA_RUNTIME_ROOT/state/runtime_strategy_log.jsonl    — append-only
  $LUKA_RUNTIME_ROOT/state/runtime_operating_mode.json   — atomic overwrite

Public API:
  run_runtime_strategy(runtime_root=None) -> dict
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from core.audit.strategy_policy import (
    OPERATING_MODES,
    STRATEGY_RECOMMENDATIONS,
    classify_operating_mode,
    recommendation_priority,
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


def _read_jsonl_last(path: Path) -> dict[str, Any] | None:
    """Read the last valid JSON line from a JSONL file."""
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        for line in reversed(lines):
            try:
                return json.loads(line)
            except Exception:
                pass
    except Exception:
        pass
    return None


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

def load_runtime_stability(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-37 stability score and drift intelligence summary."""
    state_d = _state_dir(runtime_root)
    score_data = _read_json(state_d / "runtime_stability_score.json") or {}
    intel_data = _read_json(state_d / "drift_intelligence_latest.json") or {}
    return {
        "stability_score":          int(score_data.get("score", 100)),
        "stability_classification": str(score_data.get("classification", "STABLE")),
        "hotspot_count":            len(intel_data.get("hotspot_components", [])),
        "open_finding_count":       int(intel_data.get("total_open_findings", 0)),
    }


def load_drift_intelligence(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-37 pattern registry and intelligence summary."""
    state_d = _state_dir(runtime_root)
    registry   = _read_json(state_d / "drift_pattern_registry.json") or {}
    patterns   = registry.get("patterns", [])
    return {
        "pattern_count":    len(patterns),
        "patterns":         patterns,
        "critical_patterns": [p for p in patterns
                               if p.get("default_severity", "").upper() == "CRITICAL"],
    }


def load_repair_priority(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-38 priority queue summary."""
    state_d = _state_dir(runtime_root)
    latest  = _read_json(state_d / "repair_priority_latest.json") or {}
    queue_d = _read_json(state_d / "repair_priority_queue.json") or {}
    queue   = queue_d.get("queue", [])
    p1_count = sum(1 for item in queue if item.get("priority_class") == "P1")
    p2_count = sum(1 for item in queue if item.get("priority_class") == "P2")
    return {
        "total_items":  int(latest.get("total_items", len(queue))),
        "p1_count":     p1_count,
        "p2_count":     p2_count,
        "top_priority": latest.get("top_priority"),
    }


def load_campaign_outcomes(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-41 campaign outcome intelligence."""
    state_d = _state_dir(runtime_root)
    latest      = _read_json(state_d / "repair_campaign_outcome_latest.json") or {}
    scores_data = _read_json(state_d / "campaign_effectiveness_score.json") or {}
    patterns_d  = _read_json(state_d / "campaign_pattern_registry.json") or {}

    scored      = scores_data.get("scored_campaigns", [])
    agg         = scores_data.get("aggregate_effectiveness", {})
    regressions = latest.get("regressions", [])
    patterns    = patterns_d.get("patterns", [])

    avg_eff     = float(agg.get("average_effectiveness_score", 0.0))
    total_camp  = int(agg.get("total_campaigns_scored", len(scored)))
    fail_count  = sum(1 for s in scored
                      if s.get("outcome_class") in ("CAMPAIGN_FAILED", "CAMPAIGN_REGRESSION"))
    failure_rate = fail_count / max(total_camp, 1)

    intervention_total = sum(int(s.get("operator_intervention_count", 0)) for s in scored)
    abort_total        = sum(int(s.get("wave_abort_count", 0)) for s in scored)

    high_risk_count  = sum(1 for p in patterns if p.get("recommendation") == "HIGH_RISK_PATTERN")
    abort_prone_count = sum(1 for p in patterns if p.get("pattern_class") == "abort_prone_pattern")

    return {
        "campaign_count":             total_camp,
        "avg_effectiveness_score":    avg_eff,
        "campaign_failure_rate":      round(failure_rate, 4),
        "active_regressions":         len(regressions),
        "regression_count":           int(agg.get("total_regressions_detected", len(regressions))),
        "operator_intervention_count": intervention_total,
        "high_risk_patterns":         high_risk_count,
        "abort_prone_count":          abort_prone_count,
        "overall_recommendation":     latest.get("overall_recommendation", "REVIEW_PATTERN"),
    }


# ---------------------------------------------------------------------------
# Strategy derivation
# ---------------------------------------------------------------------------

def derive_operating_mode(
    stability: dict[str, Any],
    priority: dict[str, Any],
    outcomes: dict[str, Any],
) -> dict[str, Any]:
    """Derive the current runtime operating mode from aggregated signal inputs.

    Returns: {"operating_mode": str, "confidence": float, "reasons": list[str]}
    """
    score_inputs: dict[str, Any] = {
        "stability_score":            stability.get("stability_score", 100),
        "stability_classification":   stability.get("stability_classification", "STABLE"),
        "regression_count":           outcomes.get("regression_count", 0),
        "active_regressions":         outcomes.get("active_regressions", 0),
        "operator_intervention_count": outcomes.get("operator_intervention_count", 0),
        "p1_finding_count":           priority.get("p1_count", 0),
        "campaign_failure_rate":      outcomes.get("campaign_failure_rate", 0.0),
        "avg_campaign_effectiveness": outcomes.get("avg_effectiveness_score", 0.0),
        "high_risk_patterns":         outcomes.get("high_risk_patterns", 0),
        "abort_prone_count":          outcomes.get("abort_prone_count", 0),
    }
    mode = classify_operating_mode(score_inputs)

    # Build reasons list for explainability
    reasons: list[str] = []
    cls = stability.get("stability_classification", "STABLE").upper()
    stab_score = stability.get("stability_score", 100)

    if cls in ("GOVERNANCE_RISK", "UNSTABLE"):
        reasons.append(f"runtime_stability_classification={cls}")
    if stab_score < 40:
        reasons.append(f"stability_score_critical={stab_score}")
    elif stab_score < 60:
        reasons.append(f"stability_score_degraded={stab_score}")
    if outcomes.get("active_regressions", 0) > 0:
        reasons.append(f"active_campaign_regressions={outcomes['active_regressions']}")
    if outcomes.get("high_risk_patterns", 0) > 0:
        reasons.append(f"high_risk_campaign_patterns={outcomes['high_risk_patterns']}")
    if outcomes.get("campaign_failure_rate", 0.0) >= 0.5:
        reasons.append(f"high_campaign_failure_rate={outcomes['campaign_failure_rate']:.0%}")
    if outcomes.get("operator_intervention_count", 0) >= 3:
        reasons.append(f"operator_intervention_burden={outcomes['operator_intervention_count']}")
    if priority.get("p1_count", 0) >= 5:
        reasons.append(f"critical_p1_backlog={priority['p1_count']}")
    if outcomes.get("avg_effectiveness_score", 0) >= 70 and outcomes.get("regression_count", 0) == 0:
        reasons.append("high_campaign_effectiveness_reuse_opportunity")

    if not reasons:
        reasons.append("all_signals_within_normal_bounds")

    # Confidence: high if multiple corroborating signals, lower if only one
    confidence = min(0.5 + 0.1 * len(reasons), 0.99)

    return {
        "operating_mode": mode,
        "confidence": round(confidence, 2),
        "reasons": reasons,
    }


def generate_strategy_recommendations(
    mode: str,
    stability: dict[str, Any],
    priority: dict[str, Any],
    outcomes: dict[str, Any],
    drift_intel: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate advisory strategy recommendations for the operator.

    Returns list sorted by severity (HIGH first).
    """
    recs: list[dict[str, Any]] = []
    run_idx = 0

    def _add(recommendation: str, reasons: list[str]) -> None:
        nonlocal run_idx
        run_idx += 1
        entry = STRATEGY_RECOMMENDATIONS.get(recommendation, {})
        recs.append({
            "strategy_id":             f"strategy-{run_idx:03d}",
            "recommendation":          recommendation,
            "severity":                entry.get("severity", "MEDIUM"),
            "description":             entry.get("description", ""),
            "operator_action_required": True,
            "reasons":                 reasons,
        })

    stab_cls    = stability.get("stability_classification", "STABLE").upper()
    stab_score  = stability.get("stability_score", 100)
    regressions = outcomes.get("active_regressions", 0)
    failure_rate = outcomes.get("campaign_failure_rate", 0.0)
    interventions = outcomes.get("operator_intervention_count", 0)
    p1_count    = priority.get("p1_count", 0)
    hotspots    = stability.get("hotspot_count", 0)
    high_risk_p = outcomes.get("high_risk_patterns", 0)
    overall_rec = outcomes.get("overall_recommendation", "REVIEW_PATTERN")

    # PAUSE_NEW_CAMPAIGNS
    if mode in ("STABILIZE", "HIGH_RISK_HOLD") or regressions >= 2:
        _add("PAUSE_NEW_CAMPAIGNS", [
            "active_campaign_regressions" if regressions >= 2 else f"operating_mode={mode}",
        ])

    # ISOLATE_HIGH_RISK_COMPONENTS
    if high_risk_p >= 1 or hotspots >= 3:
        _add("ISOLATE_HIGH_RISK_COMPONENTS", [
            "high_risk_campaign_patterns" if high_risk_p >= 1 else "hotspot_components_active",
        ])

    # PRIORITIZE_GOVERNANCE_FIXES
    if stab_cls in ("GOVERNANCE_RISK", "UNSTABLE") or stab_score < 40:
        _add("PRIORITIZE_GOVERNANCE_FIXES", [
            f"stability_classification={stab_cls}",
        ])

    # REDUCE_WAVE_SIZE
    if stab_cls in ("DEGRADED", "UNSTABLE", "GOVERNANCE_RISK") or mode == "CONSERVATIVE":
        _add("REDUCE_WAVE_SIZE", [
            f"stability_classification={stab_cls}",
        ])

    # REVIEW_PATTERN_BEFORE_REUSE
    if overall_rec in ("HIGH_RISK_PATTERN", "REVIEW_PATTERN") or failure_rate >= 0.4:
        _add("REVIEW_PATTERN_BEFORE_REUSE", [
            f"campaign_overall_recommendation={overall_rec}",
        ])

    # REVIEW_FAILED_CAMPAIGNS
    if failure_rate >= 0.5 or interventions >= 3:
        _add("REVIEW_FAILED_CAMPAIGNS", [
            f"campaign_failure_rate={failure_rate:.0%}" if failure_rate >= 0.5 else
            f"high_intervention_burden={interventions}",
        ])

    # CONTINUE_REPAIR_WAVE (positive signal)
    if mode in ("REPAIR_FOCUSED", "PATTERN_REUSE_CANDIDATE") and regressions == 0:
        _add("CONTINUE_REPAIR_WAVE", [
            f"operating_mode={mode}",
        ])

    # INCREASE_REPAIR_THROUGHPUT (strong positive signal)
    if mode == "REPAIR_FOCUSED" and stab_score >= 80 and p1_count >= 3:
        _add("INCREASE_REPAIR_THROUGHPUT", [
            f"p1_backlog={p1_count}",
            f"stability_score={stab_score}",
        ])

    # Sort by recommendation priority (HIGH first)
    recs.sort(key=lambda r: recommendation_priority(r["recommendation"]))
    return recs


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_runtime_strategy_report(
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Build a full AG-42 supervisory runtime strategy report."""
    stability   = load_runtime_stability(runtime_root)
    drift_intel = load_drift_intelligence(runtime_root)
    priority    = load_repair_priority(runtime_root)
    outcomes    = load_campaign_outcomes(runtime_root)

    mode_result  = derive_operating_mode(stability, priority, outcomes)
    recommendations = generate_strategy_recommendations(
        mode_result["operating_mode"], stability, priority, outcomes, drift_intel
    )

    # Key risks (top 3 by severity)
    high_recs = [r for r in recommendations if r["severity"] == "HIGH"]
    key_risks = [r["reasons"][0] if r["reasons"] else r["recommendation"]
                 for r in high_recs[:3]]

    report: dict[str, Any] = {
        "ts":           _now(),
        "run_id":       "strategy-" + uuid.uuid4().hex[:8],
        "operating_mode": mode_result["operating_mode"],
        "mode_confidence": mode_result["confidence"],
        "mode_reasons":   mode_result["reasons"],
        "recommendations": recommendations,
        "recommendation_count": len(recommendations),
        "key_risks":    key_risks,
        "stability_summary": {
            "score":          stability["stability_score"],
            "classification": stability["stability_classification"],
            "hotspot_count":  stability["hotspot_count"],
        },
        "campaign_summary": {
            "count":          outcomes["campaign_count"],
            "avg_effectiveness": outcomes["avg_effectiveness_score"],
            "failure_rate":   outcomes["campaign_failure_rate"],
            "active_regressions": outcomes["active_regressions"],
        },
        "priority_summary": {
            "p1_count": priority["p1_count"],
            "p2_count": priority["p2_count"],
            "total":    priority["total_items"],
        },
        "operator_action_required": True,
    }
    return report


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_runtime_strategy(
    report: dict[str, Any],
    runtime_root: str | None = None,
) -> None:
    """Write AG-42 outputs: append log, atomic latest, atomic mode snapshot."""
    state_d = _state_dir(runtime_root)

    # 1. Append to strategy log
    log_path = state_d / "runtime_strategy_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts":             report["ts"],
            "run_id":         report["run_id"],
            "operating_mode": report["operating_mode"],
            "recommendation_count": report["recommendation_count"],
        }) + "\n")

    # 2. Atomic latest
    _atomic_write(state_d / "runtime_strategy_latest.json", report)

    # 3. Atomic operating mode snapshot
    _atomic_write(state_d / "runtime_operating_mode.json", {
        "ts":             report["ts"],
        "run_id":         report["run_id"],
        "operating_mode": report["operating_mode"],
        "confidence":     report["mode_confidence"],
        "reasons":        report["mode_reasons"],
        "key_risks":      report["key_risks"],
    })


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_runtime_strategy(runtime_root: str | None = None) -> dict[str, Any]:
    """Run the full AG-42 supervisory runtime strategy analysis.

    Steps:
      1. Load stability, drift intelligence, repair priority, campaign outcomes
      2. Derive operating mode
      3. Generate strategy recommendations
      4. Build report
      5. Store outputs
      6. Return summary

    Never modifies governance state, campaign state, baseline, or repair artifacts.
    All outputs are advisory. Operator remains final authority.
    """
    report = build_runtime_strategy_report(runtime_root)

    try:
        store_runtime_strategy(report, runtime_root)
    except Exception as exc:
        report["storage_error"] = str(exc)

    return {
        "ok":                   True,
        "run_id":               report["run_id"],
        "operating_mode":       report["operating_mode"],
        "mode_confidence":      report["mode_confidence"],
        "recommendation_count": report["recommendation_count"],
        "key_risks":            report["key_risks"],
    }
