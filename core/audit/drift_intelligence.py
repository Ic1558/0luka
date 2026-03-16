"""AG-37: Drift Intelligence Layer.

Analyzes drift history across AG-31/32/33/34/35/36 artifacts to produce
system-level intelligence: recurring patterns, runtime stability score,
hotspot components, and advisory recommendations.

Invariants:
  - analysis-only: never modifies governance state, baseline, or canonical docs
  - never executes repair, closes findings, or changes lifecycle states
  - all outputs are advisory; operator remains final authority

Runtime outputs:
  $LUKA_RUNTIME_ROOT/state/drift_intelligence_log.jsonl   — append-only
  $LUKA_RUNTIME_ROOT/state/drift_intelligence_latest.json — atomic overwrite
  $LUKA_RUNTIME_ROOT/state/drift_pattern_registry.json    — atomic overwrite
  $LUKA_RUNTIME_ROOT/state/runtime_stability_score.json   — atomic overwrite

Public API:
  run_drift_intelligence(runtime_root=None) -> dict
"""
from __future__ import annotations

import json
import os
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from core.audit.drift_pattern_registry import (
    PATTERN_CLASSES,
    classify_drift_to_pattern,
    default_pattern_severity,
    severity_value,
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


def _read_jsonl(path: Path, limit: int = 1000) -> list[dict[str, Any]]:
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

def load_drift_history(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load AG-31 drift findings + AG-32 governance log."""
    state_d = _state_dir(runtime_root)
    findings = _read_jsonl(state_d / "drift_findings.jsonl")
    gov_log  = _read_jsonl(state_d / "drift_governance_log.jsonl")

    # Merge governance status into findings where matching finding_id exists
    status_index: dict[str, str] = {}
    for entry in gov_log:
        fid = str(entry.get("finding_id") or "")
        if fid:
            status_index[fid] = str(entry.get("new_status") or entry.get("status") or "")

    for f in findings:
        fid = str(f.get("id") or f.get("finding_id") or "")
        if fid in status_index:
            f.setdefault("gov_status", status_index[fid])
    return findings


def load_reconciliation_history(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load AG-35 reconciliation records."""
    state_d = _state_dir(runtime_root)
    records = _read_jsonl(state_d / "repair_reconciliation_log.jsonl")
    try:
        latest_path = state_d / "repair_reconciliation_latest.json"
        if latest_path.exists():
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            if latest:
                records.append(latest)
    except Exception:
        pass
    return records


def load_repair_history(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load AG-33 repair plans + AG-34 execution records."""
    state_d = _state_dir(runtime_root)
    plans      = _read_jsonl(state_d / "drift_repair_plans.jsonl")
    executions = _read_jsonl(state_d / "drift_repair_execution_log.jsonl")
    return plans + executions


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

def detect_drift_patterns(findings: list[dict[str, Any]],
                          reconciliations: list[dict[str, Any]] | None = None,
                          repairs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Detect recurring drift patterns across all history sources.

    A pattern is 'recurring' when 2+ distinct instances share the same pattern_class.
    """
    reconciliations = reconciliations or []
    repairs = repairs or []

    # Track (pattern_class → list of (component, source_id))
    class_instances: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # From AG-31 findings
    for f in findings:
        dt = str(f.get("drift_type") or f.get("drift_class") or "")
        cls = classify_drift_to_pattern(dt)
        if not cls:
            continue
        class_instances[cls].append({
            "component": str(f.get("component") or f.get("id") or ""),
            "source": "finding",
            "id": str(f.get("id") or f.get("finding_id") or ""),
        })

    # From reconciliation failures
    for r in reconciliations:
        vs = str(r.get("verification_status") or "")
        if vs in ("FAILED", "INCONCLUSIVE"):
            class_instances["recurring_reconciliation_failure"].append({
                "component": str(r.get("finding_id") or ""),
                "source": "reconciliation",
                "id": str(r.get("reconciliation_id") or ""),
            })

    # From repair execution failures
    for rep in repairs:
        if rep.get("status") == "FAILED" or rep.get("verification_status") == "FAILED":
            class_instances["recurring_failed_repair_cycle"].append({
                "component": str(rep.get("finding_id") or rep.get("plan_id") or ""),
                "source": "repair",
                "id": str(rep.get("execution_id") or rep.get("plan_id") or ""),
            })

    patterns: list[dict[str, Any]] = []
    for cls_name, instances in class_instances.items():
        if len(instances) < 2:
            continue
        # Deduplicate components
        unique_components = list(dict.fromkeys(inst["component"] for inst in instances if inst["component"]))
        severity = default_pattern_severity(cls_name)
        # Elevate severity if count is high
        count = len(instances)
        if count >= 5 and severity_value(severity) < severity_value("HIGH"):
            severity = "HIGH"
        if count >= 8 and severity_value(severity) < severity_value("CRITICAL"):
            severity = "CRITICAL"

        patterns.append({
            "pattern_id": "intel-pattern-" + uuid.uuid4().hex[:6],
            "pattern_class": cls_name,
            "affected_components": unique_components,
            "instance_count": count,
            "severity": severity,
            "ts": _now(),
        })

    # Sort by severity descending
    patterns.sort(key=lambda p: severity_value(p["severity"]), reverse=True)
    return patterns


# ---------------------------------------------------------------------------
# Stability scoring
# ---------------------------------------------------------------------------

# Stability score bands
_STABILITY_BANDS = [
    (95, "STABLE"),
    (80, "STABLE_WITH_RECURRING_DRIFT"),
    (60, "DEGRADED"),
    (40, "UNSTABLE"),
    (0,  "GOVERNANCE_RISK"),
]


def score_runtime_stability(
    findings: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    reconciliations: list[dict[str, Any]],
    repairs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Produce a deterministic runtime stability score.

    Score starts at 100 and is penalized by:
      -5  per OPEN finding
      -8  per ESCALATED finding
      -3  per governance violation (operator_gate_regression)
      -4  per recurring pattern (LOW/MEDIUM)
      -7  per recurring pattern (HIGH)
      -12 per recurring pattern (CRITICAL)
      -6  per failed repair execution
      -4  per failed reconciliation

    Score is clamped to [0, 100].
    """
    # Count governance state from findings
    open_count = 0
    escalated_count = 0
    gov_violation_count = 0

    for f in findings:
        status = str(f.get("gov_status") or f.get("status") or "")
        if status == "OPEN":
            open_count += 1
        elif status == "ESCALATED":
            escalated_count += 1
        dt = str(f.get("drift_type") or f.get("drift_class") or "")
        if dt in ("operator_gate_regression", "operator_gate_missing"):
            gov_violation_count += 1

    # Count recurring patterns by severity
    pattern_penalties = 0
    for p in patterns:
        sev = p.get("severity", "MEDIUM")
        if sev == "CRITICAL":
            pattern_penalties += 12
        elif sev == "HIGH":
            pattern_penalties += 7
        elif sev == "MEDIUM":
            pattern_penalties += 4
        else:
            pattern_penalties += 2

    # Count repair failures
    failed_repairs = sum(
        1 for r in repairs
        if r.get("status") == "FAILED" or r.get("verification_status") == "FAILED"
    )

    # Count reconciliation failures
    failed_reconciliations = sum(
        1 for r in reconciliations
        if r.get("verification_status") in ("FAILED", "INCONCLUSIVE")
    )

    score = 100
    score -= open_count * 5
    score -= escalated_count * 8
    score -= gov_violation_count * 3
    score -= pattern_penalties
    score -= failed_repairs * 6
    score -= failed_reconciliations * 4
    score = max(0, min(100, score))

    classification = "GOVERNANCE_RISK"
    for threshold, label in _STABILITY_BANDS:
        if score >= threshold:
            classification = label
            break

    return {
        "score": score,
        "classification": classification,
        "factors": {
            "open_findings": open_count,
            "escalated_findings": escalated_count,
            "governance_violations": gov_violation_count,
            "recurring_patterns": len(patterns),
            "failed_repairs": failed_repairs,
            "failed_reconciliations": failed_reconciliations,
        },
        "ts": _now(),
    }


# ---------------------------------------------------------------------------
# Hotspot analysis
# ---------------------------------------------------------------------------

def identify_drift_hotspots(findings: list[dict[str, Any]], top_n: int = 10) -> list[dict[str, Any]]:
    """Identify components with the most drift occurrences.

    Returns top_n components ranked by drift_count descending.
    """
    component_counts: Counter = Counter()
    for f in findings:
        component = str(f.get("component") or "")
        if component:
            component_counts[component] += 1

    hotspots = []
    for component, count in component_counts.most_common(top_n):
        risk = "HIGH" if count >= 5 else ("MEDIUM" if count >= 3 else "LOW")
        hotspots.append({
            "component": component,
            "drift_count": count,
            "risk": risk,
        })
    return hotspots


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def _generate_recommendations(
    patterns: list[dict[str, Any]],
    stability: dict[str, Any],
    hotspots: list[dict[str, Any]],
) -> list[str]:
    recs: list[str] = []
    classification = stability.get("classification", "")

    if classification == "GOVERNANCE_RISK":
        recs.append("CRITICAL: Investigate and resolve all governance violations before any further deployment")
    elif classification in ("UNSTABLE", "DEGRADED"):
        recs.append("Review and resolve all ESCALATED findings before introducing new features")

    critical_patterns = [p for p in patterns if p.get("severity") == "CRITICAL"]
    high_patterns = [p for p in patterns if p.get("severity") == "HIGH"]

    for p in critical_patterns:
        hint = PATTERN_CLASSES.get(p["pattern_class"], {}).get("prevention_hint", "")
        recs.append(f"CRITICAL pattern '{p['pattern_class']}' detected ({p['instance_count']}x) — {hint}")

    for p in high_patterns[:3]:
        hint = PATTERN_CLASSES.get(p["pattern_class"], {}).get("prevention_hint", "")
        recs.append(f"HIGH pattern '{p['pattern_class']}' ({p['instance_count']}x) — {hint}")

    if hotspots:
        top = hotspots[0]
        if top["risk"] in ("MEDIUM", "HIGH"):
            recs.append(f"Hotspot: '{top['component']}' has {top['drift_count']} drift occurrences — review for structural instability")

    factors = stability.get("factors", {})
    if factors.get("failed_repairs", 0) > 0:
        recs.append("Review failed repair cycles — check approved_target_files scope and action plan accuracy")
    if factors.get("failed_reconciliations", 0) > 0:
        recs.append("Repeated reconciliation failures detected — consider re-running AG-31 audit on affected components")

    if not recs:
        recs.append("No critical issues detected — system is operating within acceptable drift bounds")

    return recs


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_drift_intelligence_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Generate a full drift intelligence report from all AG-31..36 artifacts.

    Sections:
      1. total_findings_trend
      2. recurring_patterns
      3. hotspot_components
      4. repair_summary
      5. governance_risk_summary
      6. stability_score
      7. recommendations
    """
    findings       = load_drift_history(runtime_root)
    reconciliations = load_reconciliation_history(runtime_root)
    repairs        = load_repair_history(runtime_root)

    patterns  = detect_drift_patterns(findings, reconciliations, repairs)
    stability = score_runtime_stability(findings, patterns, reconciliations, repairs)
    hotspots  = identify_drift_hotspots(findings)
    recommendations = _generate_recommendations(patterns, stability, hotspots)

    # Repair summary
    plan_count   = sum(1 for r in repairs if "plan_id" in r and "execution_id" not in r)
    exec_count   = sum(1 for r in repairs if "execution_id" in r)
    failed_execs = sum(1 for r in repairs if "execution_id" in r and r.get("status") == "FAILED")
    success_execs = exec_count - failed_execs

    # Governance risk summary
    gov_violations = stability["factors"]["governance_violations"]
    escalated = stability["factors"]["escalated_findings"]

    report: dict[str, Any] = {
        "ts": _now(),
        "report_id": "intel-" + uuid.uuid4().hex[:8],
        "total_findings_trend": {
            "total_findings": len(findings),
            "open": stability["factors"]["open_findings"],
            "escalated": escalated,
        },
        "recurring_patterns": patterns,
        "hotspot_components": hotspots,
        "repair_summary": {
            "plans_generated": plan_count,
            "executions_run": exec_count,
            "executions_succeeded": success_execs,
            "executions_failed": failed_execs,
            "repair_success_rate": round(success_execs / exec_count, 2) if exec_count > 0 else None,
        },
        "governance_risk_summary": {
            "governance_violations": gov_violations,
            "escalated_findings": escalated,
            "risk_level": "CRITICAL" if gov_violations > 0 else ("HIGH" if escalated > 2 else "LOW"),
        },
        "stability_score": stability,
        "recommendations": recommendations,
    }
    return report


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_drift_intelligence(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Write AG-37 outputs: append log, atomic latest + registry + score."""
    state_d = _state_dir(runtime_root)

    # 1. Append to intelligence log
    log_path = state_d / "drift_intelligence_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Atomic latest
    _atomic_write(state_d / "drift_intelligence_latest.json", report)

    # 3. Pattern registry snapshot
    registry_snapshot = {
        "ts": _now(),
        "report_id": report.get("report_id"),
        "patterns": report.get("recurring_patterns", []),
        "total_patterns": len(report.get("recurring_patterns", [])),
    }
    _atomic_write(state_d / "drift_pattern_registry.json", registry_snapshot)

    # 4. Stability score snapshot
    _atomic_write(state_d / "runtime_stability_score.json", report.get("stability_score", {}))


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_drift_intelligence(runtime_root: str | None = None) -> dict[str, Any]:
    """Run the full AG-37 drift intelligence analysis.

    Steps:
      1. Load drift, reconciliation, repair history
      2. Detect recurring patterns
      3. Score runtime stability
      4. Identify hotspots
      5. Generate recommendations
      6. Write output artifacts
      7. Return summary

    Never modifies governance state, baseline, findings, or canonical docs.
    """
    report = generate_drift_intelligence_report(runtime_root)

    try:
        store_drift_intelligence(report, runtime_root)
    except Exception as exc:
        report["storage_error"] = str(exc)

    return {
        "ok": True,
        "report_id": report["report_id"],
        "patterns_detected": len(report["recurring_patterns"]),
        "stability_score": report["stability_score"]["score"],
        "classification": report["stability_score"]["classification"],
        "hotspots": len(report["hotspot_components"]),
        "recommendations": report["recommendations"],
    }
