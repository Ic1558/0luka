"""AG-54: Runtime Recommendation Feedback Loop.

Tracks what happens after runtime recommendations are issued:
correlates governance-gated recommendations with actual operator decisions
and emits per-recommendation feedback outcomes.

Feedback-only — no governance mutation, no decision queue mutation,
no repair execution, no baseline mutation, no automatic recommendation correction.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from runtime.recommendation_feedback_policy import (
    FEEDBACK_CLASSES,
    feedback_class_for_decision_status,
    divergence_severity_for_feedback,
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

def load_governance_gated_recommendations(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-52 governance gate — source of recommendations."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_governance_gate_latest.json") or {}
    return {
        "present": bool(latest),
        "gated_recommendations": latest.get("gated_recommendations", []),
        "total_count": latest.get("total_count", 0),
    }


def load_decision_queue_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-44 decision queue state."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "decision_queue_governance_latest.json") or {}
    return {
        "present": bool(latest),
        "open_count": latest.get("open_count", 0),
        "entries": latest.get("entries", []),
    }


def load_operator_decision_history(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-45 operator decision memory."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "operator_decision_memory_latest.json") or {}
    inbox = _read_jsonl(Path(rt) / "state" / "operator_inbox.jsonl")
    return {
        "present": bool(latest),
        "memory_entries": latest.get("memory_entries", []),
        "inbox_entries": inbox,
    }


# ---------------------------------------------------------------------------
# Correlation logic
# ---------------------------------------------------------------------------

def classify_feedback_outcome(
    rec: dict[str, Any],
    decision_queue: dict[str, Any],
    decision_history: dict[str, Any],
) -> dict[str, Any]:
    """Classify feedback outcome for one recommendation."""
    rec_id = rec.get("recommendation_id") or rec.get("guidance_id") or "unknown"

    # Look for a matching decision entry
    matched_decision: dict[str, Any] | None = None

    # Check decision queue entries
    for entry in decision_queue.get("entries", []):
        target = entry.get("target_ref") or entry.get("recommendation_id") or ""
        if target == rec_id or entry.get("decision_id", "").startswith(rec_id[:6]):
            matched_decision = entry
            break

    # Check operator inbox
    if matched_decision is None:
        for entry in decision_history.get("inbox_entries", []):
            task_id = entry.get("task_id") or entry.get("id") or ""
            if rec_id in task_id or task_id in rec_id:
                matched_decision = entry
                break

    # Check memory entries
    if matched_decision is None:
        for entry in decision_history.get("memory_entries", []):
            if entry.get("recommendation_id") == rec_id:
                matched_decision = entry
                break

    # Derive feedback class
    if matched_decision is None:
        # No decision found — determine IGNORED vs DEFERRED
        if decision_queue.get("present") and decision_queue.get("open_count", 0) > 0:
            feedback_class = "DEFERRED"
            summary = "Recommendation entered queue but no matching decision found; treated as deferred."
            decision_id = None
        else:
            feedback_class = "IGNORED"
            summary = "No operator decision found for this recommendation."
            decision_id = None
    else:
        status = matched_decision.get("status") or matched_decision.get("decision_status") or ""
        feedback_class = feedback_class_for_decision_status(status)
        decision_id = (
            matched_decision.get("decision_id")
            or matched_decision.get("task_id")
            or matched_decision.get("id")
        )
        summary = f"Recommendation matched decision. Status='{status}' → feedback='{feedback_class}'."

    return {
        "recommendation_id": rec_id,
        "decision_id": decision_id,
        "feedback_class": feedback_class,
        "divergence_severity": divergence_severity_for_feedback(feedback_class),
        "summary": summary,
        "evidence_refs": [
            "runtime_governance_gate_latest.json",
            "decision_queue_governance_latest.json",
        ],
    }


def correlate_recommendations_with_decisions(
    gated_recs: list[dict[str, Any]],
    decision_queue: dict[str, Any],
    decision_history: dict[str, Any],
) -> list[dict[str, Any]]:
    """Correlate all governance-gated recommendations with operator decisions."""
    return [
        classify_feedback_outcome(rec, decision_queue, decision_history)
        for rec in gated_recs
    ]


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_recommendation_feedback_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the AG-54 recommendation feedback report."""
    rt = _rt(runtime_root)

    gate_data    = load_governance_gated_recommendations(rt)
    queue_data   = load_decision_queue_state(rt)
    history_data = load_operator_decision_history(rt)

    gated_recs = gate_data.get("gated_recommendations", [])
    feedback_entries = correlate_recommendations_with_decisions(
        gated_recs, queue_data, history_data
    )

    # Summarise
    counts: dict[str, int] = {cls: 0 for cls in FEEDBACK_CLASSES}
    for entry in feedback_entries:
        cls = entry.get("feedback_class", "INCONCLUSIVE")
        counts[cls] = counts.get(cls, 0) + 1

    gaps = [e for e in feedback_entries if e["feedback_class"] in ("IGNORED", "OVERRIDDEN")]

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":                    ts,
        "run_id":                str(uuid.uuid4()),
        "recommendations_total": len(feedback_entries),
        "feedback_counts":       counts,
        "feedback_entries":      feedback_entries,
        "gaps":                  gaps,
        "evidence_refs": [
            "runtime_governance_gate_latest.json",
            "decision_queue_governance_latest.json",
            "operator_decision_memory_latest.json",
        ],
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_recommendation_feedback(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist AG-54 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_recommendation_feedback_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    _atomic_write(state_dir / "runtime_recommendation_feedback_latest.json", report)

    # 3. Slim index (atomic)
    index = {
        "ts":                    report["ts"],
        "run_id":                report["run_id"],
        "recommendations_total": report["recommendations_total"],
        "feedback_counts":       report["feedback_counts"],
        "gap_count":             len(report["gaps"]),
    }
    _atomic_write(state_dir / "runtime_recommendation_feedback_index.json", index)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_recommendation_feedback(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-54 recommendation feedback loop and persist outputs."""
    try:
        report = build_recommendation_feedback_report(runtime_root)
        store_recommendation_feedback(report, runtime_root)
        return {
            "ok":                    True,
            "recommendations_total": report["recommendations_total"],
            "feedback_counts":       report["feedback_counts"],
            "gap_count":             len(report["gaps"]),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
