"""AG-45: Operator Decision Session Memory.

Aggregates prior decision queue history to detect recurrence patterns,
build session memory summaries, and attach continuity context to current
open decisions.

Context-memory only — no governance mutation, no queue mutation, no campaign
mutation, no repair execution, no baseline modification, no auto-updates to
decision outcomes.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from core.audit.decision_memory_policy import (
    GOVERNANCE_REVIEW_TYPES,
    HIGH_RISK_DECISION_TYPES,
    MEMORY_PATTERNS,
    PAUSE_CAMPAIGN_TYPES,
    recurrence_threshold_for,
    should_attach_memory_context,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rt(runtime_root: str | None) -> str:
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
    rows = []
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

def load_decision_queue_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load combined queue state from AG-44 outputs."""
    rt = _rt(runtime_root)
    state: dict[str, Any] = {}

    latest = _read_json(Path(rt) / "state" / "decision_queue_governance_latest.json")
    if latest:
        state["latest"] = latest

    queue_state = _read_json(Path(rt) / "state" / "decision_queue_state.json")
    if queue_state:
        state["entries"] = queue_state.get("entries", {})

    log_rows = _read_jsonl(Path(rt) / "state" / "decision_queue_log.jsonl")
    state["log"] = log_rows
    return state


def load_decision_history(runtime_root: str | None = None) -> list[dict]:
    """Load historical decision records from AG-43 + AG-44 outputs."""
    rt = _rt(runtime_root)
    history: list[dict] = []

    # AG-43 append log — every package ever generated
    history.extend(_read_jsonl(Path(rt) / "state" / "operator_decision_packages.jsonl"))

    # AG-44 queue governance log — every queue run
    history.extend(_read_jsonl(Path(rt) / "state" / "decision_queue_governance_log.jsonl"))

    return history


def load_decision_packages(runtime_root: str | None = None) -> list[dict]:
    """Load current open decision packages from AG-43."""
    rt = _rt(runtime_root)
    data = _read_json(Path(rt) / "state" / "operator_decision_queue.json")
    if data is None:
        return []
    return data.get("packages", [])


def load_campaign_outcomes(runtime_root: str | None = None) -> dict[str, Any]:
    """Load campaign outcome intelligence from AG-41 / AG-42."""
    rt = _rt(runtime_root)
    outcomes: dict[str, Any] = {}

    latest = _read_json(Path(rt) / "state" / "repair_campaign_outcome_latest.json")
    if latest:
        outcomes["campaign_outcome"] = latest

    strategy = _read_json(Path(rt) / "state" / "runtime_strategy_latest.json")
    if strategy:
        outcomes["strategy"] = strategy

    return outcomes


# ---------------------------------------------------------------------------
# Recurrence detection
# ---------------------------------------------------------------------------

def detect_decision_recurrence(
    history: list[dict],
    queue_state_entries: dict[str, Any],
    queue_log: list[dict],
) -> list[dict]:
    """Detect recurrence patterns across historical decision records.

    Returns a list of recurrence observations — one per (pattern, target) pair.
    """
    # Build index: (decision_type, target_ref) → list of events
    event_index: dict[tuple[str, str], list[dict]] = defaultdict(list)

    # From AG-43 packages
    for pkg in history:
        dtype  = str(pkg.get("decision_type", ""))
        target = str(pkg.get("target_ref", ""))
        if dtype:
            event_index[(dtype, target)].append({
                "decision_id": pkg.get("decision_id", ""),
                "ts":          pkg.get("ts", ""),
                "status":      pkg.get("status", "PROPOSED"),
                "source":      "ag43_package",
            })

    # From AG-44 transition log
    for row in queue_log:
        did    = str(row.get("decision_id", ""))
        status = str(row.get("new_status", ""))
        # Look up type/target from queue_state_entries
        event_index[("__transition__", did)].append({
            "decision_id": did,
            "ts":          row.get("ts", ""),
            "status":      status,
            "source":      "queue_log",
        })

    # Build deferral / supersede counts per (type, target)
    deferral_counts:  dict[tuple[str, str], list[str]] = defaultdict(list)
    supersede_counts: dict[tuple[str, str], list[str]] = defaultdict(list)
    reopen_counts:    dict[tuple[str, str], list[str]] = defaultdict(list)

    for (dtype, target), events in event_index.items():
        if dtype == "__transition__":
            continue
        for ev in events:
            s = ev.get("status", "")
            did = ev.get("decision_id", "")
            if s == "DEFERRED":
                deferral_counts[(dtype, target)].append(did)
            elif s == "SUPERSEDED":
                supersede_counts[(dtype, target)].append(did)
            elif s == "OPEN" and ev.get("source") == "queue_log":
                reopen_counts[(dtype, target)].append(did)

    # Also scan queue_log for deferred/superseded/reopen transitions
    for row in queue_log:
        did       = str(row.get("decision_id", ""))
        new_st    = str(row.get("new_status", ""))
        # Find type/target from ag43 packages
        for (dtype, target), events in event_index.items():
            if dtype == "__transition__":
                continue
            matching_dids = [ev["decision_id"] for ev in events]
            if did in matching_dids:
                if new_st == "DEFERRED":
                    deferral_counts[(dtype, target)].append(did)
                elif new_st == "SUPERSEDED":
                    supersede_counts[(dtype, target)].append(did)
                elif new_st == "OPEN":
                    reopen_counts[(dtype, target)].append(did)

    recurrences: list[dict] = []

    # Repeated deferral pattern
    thresh = recurrence_threshold_for("repeated_deferral_pattern")
    for (dtype, target), dids in deferral_counts.items():
        uniq = list(set(dids))
        if len(uniq) >= thresh:
            recurrences.append({
                "pattern": "repeated_deferral_pattern",
                "decision_type": dtype,
                "target_ref": target,
                "count": len(uniq),
                "decision_ids": uniq,
            })

    # Repeated supersede pattern
    thresh = recurrence_threshold_for("repeated_supersede_pattern")
    for (dtype, target), dids in supersede_counts.items():
        uniq = list(set(dids))
        if len(uniq) >= thresh:
            recurrences.append({
                "pattern": "repeated_supersede_pattern",
                "decision_type": dtype,
                "target_ref": target,
                "count": len(uniq),
                "decision_ids": uniq,
            })

    # Stale → reopen pattern
    thresh = recurrence_threshold_for("stale_decision_reopen_pattern")
    for (dtype, target), dids in reopen_counts.items():
        uniq = list(set(dids))
        if len(uniq) >= thresh:
            recurrences.append({
                "pattern": "stale_decision_reopen_pattern",
                "decision_type": dtype,
                "target_ref": target,
                "count": len(uniq),
                "decision_ids": uniq,
            })

    # High-risk recurring decision
    thresh = recurrence_threshold_for("recurring_high_risk_component_decision")
    for (dtype, target), events in event_index.items():
        if dtype in HIGH_RISK_DECISION_TYPES and len(events) >= thresh:
            dids = [ev["decision_id"] for ev in events]
            recurrences.append({
                "pattern": "recurring_high_risk_component_decision",
                "decision_type": dtype,
                "target_ref": target,
                "count": len(events),
                "decision_ids": list(set(dids)),
            })

    # Recurring governance review requirement
    thresh = recurrence_threshold_for("recurring_governance_review_requirement")
    for (dtype, target), events in event_index.items():
        if dtype in GOVERNANCE_REVIEW_TYPES and len(events) >= thresh:
            dids = [ev["decision_id"] for ev in events]
            recurrences.append({
                "pattern": "recurring_governance_review_requirement",
                "decision_type": dtype,
                "target_ref": target,
                "count": len(events),
                "decision_ids": list(set(dids)),
            })

    # Repeated pause campaign recommendation
    thresh = recurrence_threshold_for("repeated_pause_campaign_recommendation")
    for (dtype, target), events in event_index.items():
        if dtype in PAUSE_CAMPAIGN_TYPES and len(events) >= thresh:
            dids = [ev["decision_id"] for ev in events]
            recurrences.append({
                "pattern": "repeated_pause_campaign_recommendation",
                "decision_type": dtype,
                "target_ref": target,
                "count": len(events),
                "decision_ids": list(set(dids)),
            })

    return recurrences


# ---------------------------------------------------------------------------
# Session memory builder
# ---------------------------------------------------------------------------

def build_decision_session_memory(
    recurrences: list[dict],
    queue_state_entries: dict[str, Any],
) -> list[dict]:
    """Build session memory entries from detected recurrences."""
    memories: list[dict] = []
    for rec in recurrences:
        pattern  = rec["pattern"]
        dtype    = rec["decision_type"]
        target   = rec.get("target_ref", "")
        dids     = rec.get("decision_ids", [])

        # Determine last outcome from queue state
        last_outcome = None
        for did in reversed(dids):
            entry = queue_state_entries.get(did, {})
            if entry.get("status"):
                last_outcome = entry["status"]
                break
        if last_outcome is None and dids:
            last_outcome = "PROPOSED"

        summary = _summarise_pattern(pattern, dtype, target, rec["count"])

        memories.append({
            "memory_id":          f"mem-{uuid.uuid4().hex[:8]}",
            "decision_type":      dtype,
            "target_ref":         target,
            "recurrence_class":   pattern,
            "prior_occurrences":  rec["count"],
            "last_outcome":       last_outcome,
            "related_decision_ids": dids,
            "summary":            summary,
            "evidence_refs":      _evidence_refs_for(pattern),
        })

    return memories


def _summarise_pattern(pattern: str, dtype: str, target: str, count: int) -> str:
    target_str = f" for {target!r}" if target else ""
    if pattern == "repeated_deferral_pattern":
        return (
            f"{dtype}{target_str} has been deferred {count} time(s). "
            "Consider resolving underlying blockers before re-queuing."
        )
    if pattern == "repeated_supersede_pattern":
        return (
            f"{dtype}{target_str} has been superseded {count} time(s). "
            "Review whether underlying conditions have changed."
        )
    if pattern == "recurring_high_risk_component_decision":
        return (
            f"High-risk component decision ({dtype}){target_str} "
            f"has recurred {count} time(s). Escalation review may be warranted."
        )
    if pattern == "recurring_governance_review_requirement":
        return (
            f"Governance review has been required {count} time(s){target_str}. "
            "Governance lifecycle may need attention."
        )
    if pattern == "stale_decision_reopen_pattern":
        return (
            f"{dtype}{target_str} has been reopened {count} time(s) after going stale. "
            "Investigate why it cannot be resolved."
        )
    if pattern == "repeated_pause_campaign_recommendation":
        return (
            f"Campaign pause recommendation has recurred {count} time(s){target_str}. "
            "Underlying instability may be persistent."
        )
    return f"Recurrence pattern {pattern!r} detected {count} time(s){target_str}."


def _evidence_refs_for(pattern: str) -> list[str]:
    base = ["operator_decision_packages.jsonl", "decision_queue_log.jsonl"]
    if "governance" in pattern:
        base.append("runtime_strategy_latest.json")
    if "campaign" in pattern or "pause" in pattern:
        base.append("repair_campaign_outcome_latest.json")
    return base


# ---------------------------------------------------------------------------
# Context attachment
# ---------------------------------------------------------------------------

def attach_memory_context_to_open_decisions(
    packages: list[dict],
    memories: list[dict],
) -> list[dict]:
    """Enrich current OPEN decisions with memory context references.

    Does NOT change queue priority or decision state — context-only.
    """
    enriched = []
    for pkg in packages:
        pkg = dict(pkg)  # shallow copy — do not mutate caller's list
        relevant = [
            {"memory_id": m["memory_id"], "recurrence_class": m["recurrence_class"],
             "summary": m["summary"], "prior_occurrences": m["prior_occurrences"]}
            for m in memories
            if should_attach_memory_context(pkg, m)
        ]
        if relevant:
            pkg["memory_context"] = relevant
        enriched.append(pkg)
    return enriched


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_decision_memory_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the AG-45 operator decision session memory report."""
    rt = _rt(runtime_root)

    queue_state     = load_decision_queue_state(rt)
    history         = load_decision_history(rt)
    packages        = load_decision_packages(rt)
    campaign_outcomes = load_campaign_outcomes(rt)

    state_entries = queue_state.get("entries", {})
    queue_log     = queue_state.get("log", [])

    recurrences = detect_decision_recurrence(history, state_entries, queue_log)
    memories    = build_decision_session_memory(recurrences, state_entries)
    enriched_packages = attach_memory_context_to_open_decisions(packages, memories)

    # Summary stats
    pattern_counts: dict[str, int] = {}
    for m in memories:
        rc = m["recurrence_class"]
        pattern_counts[rc] = pattern_counts.get(rc, 0) + 1

    top_pattern = max(pattern_counts, key=lambda k: pattern_counts[k]) if pattern_counts else None

    repeated_deferrals = sum(
        1 for m in memories if m["recurrence_class"] == "repeated_deferral_pattern"
    )
    repeated_supersedes = sum(
        1 for m in memories if m["recurrence_class"] == "repeated_supersede_pattern"
    )

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":                    ts,
        "run_id":                str(uuid.uuid4()),
        "memory_entries":        len(memories),
        "memories":              memories,
        "enriched_packages":     enriched_packages,
        "pattern_counts":        pattern_counts,
        "top_pattern":           top_pattern,
        "repeated_deferrals":    repeated_deferrals,
        "repeated_supersedes":   repeated_supersedes,
        "total_history_records": len(history),
        "operator_action_required": True,
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_decision_memory(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist AG-45 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "operator_decision_memory_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    latest_path = state_dir / "operator_decision_memory_latest.json"
    _atomic_write(latest_path, report)

    # 3. Memory index — slim list of memory entries
    index = {
        "ts":             report["ts"],
        "run_id":         report["run_id"],
        "memory_entries": report["memory_entries"],
        "top_pattern":    report["top_pattern"],
        "index":          [
            {
                "memory_id":        m["memory_id"],
                "decision_type":    m["decision_type"],
                "target_ref":       m["target_ref"],
                "recurrence_class": m["recurrence_class"],
                "prior_occurrences": m["prior_occurrences"],
            }
            for m in report.get("memories", [])
        ],
    }
    index_path = state_dir / "operator_decision_memory_index.json"
    _atomic_write(index_path, index)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_operator_decision_memory(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-45 decision session memory and persist outputs."""
    try:
        report = build_decision_memory_report(runtime_root)
        store_decision_memory(report, runtime_root)
        return {
            "ok":             True,
            "memory_entries": report["memory_entries"],
            "top_pattern":    report["top_pattern"],
            "repeated_deferrals": report["repeated_deferrals"],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
