"""AG-41: Repair Campaign Outcome Intelligence.

Reads AG-40 campaign history and AG-34/35 repair+reconciliation evidence to
produce campaign-level outcome intelligence: effectiveness scores, regression
detection, pattern analysis, and operator recommendations.

Invariants:
  - intelligence-only: never mutates campaign state, executes repairs,
    modifies governance state, or touches audit_baseline
  - all recommendations are advisory; operator remains final authority
  - deterministic given the same input history

Runtime outputs:
  $LUKA_RUNTIME_ROOT/state/repair_campaign_outcome_log.jsonl   — append-only
  $LUKA_RUNTIME_ROOT/state/repair_campaign_outcome_latest.json — atomic overwrite
  $LUKA_RUNTIME_ROOT/state/campaign_effectiveness_score.json   — atomic overwrite
  $LUKA_RUNTIME_ROOT/state/campaign_pattern_registry.json      — atomic overwrite

Public API:
  run_campaign_outcome_intelligence(runtime_root=None) -> dict
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from core.audit.campaign_pattern_registry import (
    CAMPAIGN_OUTCOME_CLASSES,
    CAMPAIGN_RECOMMENDATION_CLASSES,
    classify_campaign_patterns,
    recommendation_for_pattern,
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


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
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

def load_campaign_history(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load AG-40 campaign records from repair_campaign_log.jsonl.

    Returns empty list if AG-40 has not yet run (graceful fallback).
    """
    state_d = _state_dir(runtime_root)
    return _read_jsonl(state_d / "repair_campaign_log.jsonl")


def load_wave_history(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load AG-39 wave events from repair_wave_log.jsonl."""
    state_d = _state_dir(runtime_root)
    return _read_jsonl(state_d / "repair_wave_log.jsonl")


def load_reconciliation_history(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load AG-35 reconciliation records."""
    state_d = _state_dir(runtime_root)
    return _read_jsonl(state_d / "repair_reconciliation_log.jsonl")


def load_repair_execution_history(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load AG-34 execution records."""
    state_d = _state_dir(runtime_root)
    return _read_jsonl(state_d / "drift_repair_execution_log.jsonl")


# ---------------------------------------------------------------------------
# Derived indexes
# ---------------------------------------------------------------------------

def _build_wave_event_index(wave_history: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group wave events by campaign_id (if tagged) or wave_id."""
    index: dict[str, list[dict[str, Any]]] = {}
    for rec in wave_history:
        key = str(rec.get("campaign_id") or rec.get("wave_id") or "")
        if key:
            index.setdefault(key, []).append(rec)
    return index


def _build_recon_index(recon_history: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group reconciliation records by finding_id."""
    index: dict[str, list[dict[str, Any]]] = {}
    for rec in recon_history:
        fid = str(rec.get("finding_id") or "")
        if fid:
            index.setdefault(fid, []).append(rec)
    return index


def _build_exec_index(exec_history: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index execution records by execution_id."""
    return {str(r.get("execution_id") or ""): r for r in exec_history if r.get("execution_id")}


# ---------------------------------------------------------------------------
# Effectiveness scoring
# ---------------------------------------------------------------------------

def score_campaign_effectiveness(
    campaign: dict[str, Any],
    recon_index: dict[str, list[dict[str, Any]]] | None = None,
    exec_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute a deterministic effectiveness score for a single campaign.

    Metrics computed:
      - repair_success_rate
      - reconciliation_pass_ratio
      - regression_count
      - operator_intervention_count
      - wave_pause_count / wave_abort_count
      - findings_targeted / findings_resolved
      - effectiveness_score (0–100)
      - outcome_class
      - recommendation

    Returns full metrics dict.
    """
    recon_index = recon_index or {}
    exec_index = exec_index or {}

    campaign_id = str(campaign.get("campaign_id") or campaign.get("id") or "unknown")
    findings_targeted = int(campaign.get("findings_targeted", 0) or
                            len(campaign.get("finding_ids", [])))
    findings_resolved  = int(campaign.get("findings_resolved", 0))
    wave_count         = int(campaign.get("total_waves", 0) or campaign.get("wave_count", 0))
    wave_abort_count   = int(campaign.get("wave_abort_count", 0))
    wave_pause_count   = int(campaign.get("wave_pause_count", 0))
    intervention_count = int(campaign.get("operator_intervention_count", 0))
    regression_count   = int(campaign.get("regression_count", 0))

    # Repair success rate from execution index if available
    exec_ids = campaign.get("execution_ids", [])
    if exec_ids and exec_index:
        passed = sum(1 for eid in exec_ids
                     if exec_index.get(str(eid), {}).get("status") in ("COMPLETED", "VERIFIED"))
        repair_success_rate = passed / max(len(exec_ids), 1)
    elif findings_targeted > 0:
        repair_success_rate = findings_resolved / findings_targeted
    else:
        repair_success_rate = 0.0

    # Reconciliation pass ratio from recon index
    finding_ids = campaign.get("finding_ids", [])
    if finding_ids and recon_index:
        recon_passed = 0
        recon_total = 0
        for fid in finding_ids:
            recs = recon_index.get(str(fid), [])
            if recs:
                recon_total += 1
                last = recs[-1]
                if last.get("governance_recommendation", "").startswith("recommend_RESOLVED"):
                    recon_passed += 1
        reconciliation_pass_ratio = recon_passed / max(recon_total, 1) if recon_total else 0.0
    else:
        reconciliation_pass_ratio = repair_success_rate  # best estimate

    # Build score from components (0–100)
    score = 0

    # Base from repair success (0–40)
    score += int(repair_success_rate * 40)

    # Reconciliation contribution (0–25)
    score += int(reconciliation_pass_ratio * 25)

    # Regression penalty (-15 per regression, capped at -30)
    score -= min(regression_count * 15, 30)

    # Intervention penalty (-5 per intervention beyond 1, capped at -15)
    score -= min(max(intervention_count - 1, 0) * 5, 15)

    # Abort penalty (-10 per abort, capped at -20)
    score -= min(wave_abort_count * 10, 20)

    # Bonus for clean completion (all waves, no pause/abort, no regression)
    if wave_abort_count == 0 and wave_pause_count == 0 and regression_count == 0 and repair_success_rate >= 0.8:
        score += 10

    score = max(0, min(100, score))

    # Outcome class
    if regression_count > 0 and repair_success_rate < 0.3:
        outcome_class = "CAMPAIGN_REGRESSION"
    elif score >= 75:
        outcome_class = "CAMPAIGN_SUCCESS"
    elif score >= 45:
        outcome_class = "CAMPAIGN_PARTIAL"
    elif score <= 20 and wave_count > 0:
        outcome_class = "CAMPAIGN_FAILED"
    elif findings_targeted == 0:
        outcome_class = "CAMPAIGN_INCONCLUSIVE"
    else:
        outcome_class = "CAMPAIGN_INCONCLUSIVE"

    metrics: dict[str, Any] = {
        "campaign_id":                campaign_id,
        "effectiveness_score":        score,
        "outcome_class":              outcome_class,
        "repair_success_rate":        round(repair_success_rate, 4),
        "reconciliation_pass_ratio":  round(reconciliation_pass_ratio, 4),
        "regression_count":           regression_count,
        "operator_intervention_count": intervention_count,
        "wave_pause_count":           wave_pause_count,
        "wave_abort_count":           wave_abort_count,
        "total_waves":                wave_count,
        "findings_targeted":          findings_targeted,
        "findings_resolved":          findings_resolved,
        "ts_scored":                  _now(),
    }
    return metrics


# ---------------------------------------------------------------------------
# Regression detection
# ---------------------------------------------------------------------------

def detect_campaign_regressions(
    campaigns: list[dict[str, Any]],
    recon_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Identify campaigns associated with post-campaign drift regression.

    A regression is flagged when:
      - reconciliation records following campaign execution show REGRESSED status
      - OR campaign explicitly records regression_count > 0
    """
    regressions: list[dict[str, Any]] = []

    # Build set of finding_ids with REGRESSED reconciliation outcome
    regressed_fids: set[str] = set()
    for rec in recon_history:
        drift_state = str(rec.get("drift_recheck_result") or "")
        rec_gov = str(rec.get("governance_recommendation") or "")
        if "REGRESSED" in drift_state or "HIGH_PRIORITY_ESCALATION" in rec_gov:
            fid = str(rec.get("finding_id") or "")
            if fid:
                regressed_fids.add(fid)

    for campaign in campaigns:
        cid = str(campaign.get("campaign_id") or campaign.get("id") or "")
        explicit_regressions = int(campaign.get("regression_count", 0))
        finding_ids = set(str(f) for f in campaign.get("finding_ids", []))
        recon_regressions = finding_ids & regressed_fids

        if explicit_regressions > 0 or recon_regressions:
            regressions.append({
                "campaign_id":           cid,
                "explicit_regressions":  explicit_regressions,
                "reconciliation_regressions": list(recon_regressions),
                "total_regression_signals": explicit_regressions + len(recon_regressions),
                "ts_detected": _now(),
            })

    return regressions


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

def detect_campaign_patterns(
    scored_campaigns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect campaign-level patterns across scored campaigns.

    Groups campaigns by applicable pattern class.
    Returns list of pattern records with affected_campaign_ids and recommendation.
    """
    pattern_buckets: dict[str, list[str]] = {}
    for metrics in scored_campaigns:
        applicable = classify_campaign_patterns(metrics)
        for pclass in applicable:
            pattern_buckets.setdefault(pclass, []).append(metrics["campaign_id"])

    patterns: list[dict[str, Any]] = []
    for pclass, cids in pattern_buckets.items():
        patterns.append({
            "pattern_class":         pclass,
            "affected_campaign_ids": cids,
            "campaign_count":        len(cids),
            "recommendation":        recommendation_for_pattern(pclass),
            "ts_detected":           _now(),
        })

    # Sort for determinism: by pattern_class name
    patterns.sort(key=lambda p: p["pattern_class"])
    return patterns


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_campaign_outcome_report(
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Generate a full AG-41 campaign outcome intelligence report.

    Sections:
      1. campaign_count
      2. scored_campaigns
      3. regressions
      4. patterns
      5. aggregate_effectiveness
      6. recommendations
      7. outcome_distribution
    """
    campaigns    = load_campaign_history(runtime_root)
    wave_events  = load_wave_history(runtime_root)
    recon_history = load_reconciliation_history(runtime_root)
    exec_history  = load_repair_execution_history(runtime_root)

    recon_index = _build_recon_index(recon_history)
    exec_index  = _build_exec_index(exec_history)

    # Score each campaign
    scored: list[dict[str, Any]] = []
    for campaign in campaigns:
        metrics = score_campaign_effectiveness(campaign, recon_index, exec_index)
        scored.append(metrics)

    # Detect regressions
    regressions = detect_campaign_regressions(campaigns, recon_history)

    # Detect patterns
    patterns = detect_campaign_patterns(scored)

    # Aggregate effectiveness
    if scored:
        avg_score = sum(m["effectiveness_score"] for m in scored) / len(scored)
        avg_success_rate = sum(m["repair_success_rate"] for m in scored) / len(scored)
    else:
        avg_score = 0.0
        avg_success_rate = 0.0

    # Outcome distribution
    outcome_dist: dict[str, int] = {}
    for m in scored:
        oc = m["outcome_class"]
        outcome_dist[oc] = outcome_dist.get(oc, 0) + 1

    # Aggregate recommendation
    high_risk_count = sum(1 for p in patterns if p["recommendation"] == "HIGH_RISK_PATTERN")
    retire_count    = sum(1 for p in patterns if p["recommendation"] == "RETIRE_PATTERN")
    continue_count  = sum(1 for p in patterns if p["recommendation"] == "CONTINUE_PATTERN")

    if high_risk_count > 0:
        overall_recommendation = "HIGH_RISK_PATTERN"
    elif retire_count > 0:
        overall_recommendation = "RETIRE_PATTERN"
    elif continue_count > 0 and len(regressions) == 0:
        overall_recommendation = "CONTINUE_PATTERN"
    else:
        overall_recommendation = "REVIEW_PATTERN"

    report: dict[str, Any] = {
        "ts":                     _now(),
        "run_id":                 "campaign-intel-" + uuid.uuid4().hex[:8],
        "campaign_count":         len(campaigns),
        "scored_campaigns":       scored,
        "regressions":            regressions,
        "patterns":               patterns,
        "aggregate_effectiveness": {
            "average_effectiveness_score": round(avg_score, 2),
            "average_repair_success_rate": round(avg_success_rate, 4),
            "total_regressions_detected":  len(regressions),
            "pattern_count":               len(patterns),
        },
        "outcome_distribution":   outcome_dist,
        "overall_recommendation": overall_recommendation,
        "operator_action_required": True,
    }
    return report


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_campaign_outcome_intelligence(
    report: dict[str, Any],
    runtime_root: str | None = None,
) -> None:
    """Write AG-41 outputs atomically."""
    state_d = _state_dir(runtime_root)

    # 1. Append to outcome log
    log_path = state_d / "repair_campaign_outcome_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts":          report["ts"],
            "run_id":      report["run_id"],
            "campaign_count": report["campaign_count"],
            "overall_recommendation": report["overall_recommendation"],
        }) + "\n")

    # 2. Atomic latest
    _atomic_write(state_d / "repair_campaign_outcome_latest.json", report)

    # 3. Effectiveness scores snapshot
    _atomic_write(state_d / "campaign_effectiveness_score.json", {
        "ts": report["ts"],
        "run_id": report["run_id"],
        "scored_campaigns": report["scored_campaigns"],
        "aggregate_effectiveness": report["aggregate_effectiveness"],
        "outcome_distribution": report["outcome_distribution"],
    })

    # 4. Campaign pattern registry snapshot
    _atomic_write(state_d / "campaign_pattern_registry.json", {
        "ts": report["ts"],
        "run_id": report["run_id"],
        "patterns": report["patterns"],
        "overall_recommendation": report["overall_recommendation"],
    })


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_campaign_outcome_intelligence(runtime_root: str | None = None) -> dict[str, Any]:
    """Run the full AG-41 campaign outcome intelligence analysis.

    Steps:
      1. Load campaign, wave, reconciliation, execution history
      2. Score each campaign
      3. Detect regressions
      4. Detect patterns
      5. Generate report
      6. Store outputs
      7. Return summary

    Never modifies campaign state, governance state, baseline, findings, or repair artifacts.
    """
    report = generate_campaign_outcome_report(runtime_root)

    try:
        store_campaign_outcome_intelligence(report, runtime_root)
    except Exception as exc:
        report["storage_error"] = str(exc)

    return {
        "ok": True,
        "run_id":            report["run_id"],
        "campaign_count":    report["campaign_count"],
        "patterns_detected": len(report["patterns"]),
        "regressions_found": len(report["regressions"]),
        "overall_recommendation": report["overall_recommendation"],
        "aggregate_effectiveness": report["aggregate_effectiveness"],
    }
