"""AG-44: Supervisory Decision Queue Governance.

Manages the full lifecycle of operator decision packages:
  - Load packages from AG-43 outputs
  - Classify queue priority (Q1..Q4)
  - Build prioritised decision queue
  - Lifecycle transitions: defer / reopen / supersede / archive
  - Automatic stale-expiry
  - Persist queue state

Pure orchestrator — no governance mutation, no campaign mutation,
no repair execution, no auto-approval.
operator_action_required always preserved.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from core.audit.decision_queue_policy import (
    STALE_DECISION_POLICY,
    classify_age_bucket,
    classify_queue_priority_class,
    queue_priority_rank,
    score_queue_entry,
    valid_queue_status_transition,
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
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            lines.append(json.loads(raw))
        except Exception:
            continue
    return lines


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_decision_packages(runtime_root: str | None = None) -> list[dict]:
    """Load current operator decision packages from AG-43 queue output."""
    rt = _rt(runtime_root)
    path = Path(rt) / "state" / "operator_decision_queue.json"
    data = _read_json(path)
    if data is None:
        return []
    return data.get("packages", [])


def load_queue_state(runtime_root: str | None = None) -> dict[str, Any]:
    """Load persisted queue state (decision_id → status / metadata)."""
    rt = _rt(runtime_root)
    path = Path(rt) / "state" / "decision_queue_state.json"
    data = _read_json(path)
    if data is None:
        return {}
    return data.get("entries", {})


def load_operating_mode(runtime_root: str | None = None) -> str:
    """Load current operating mode from AG-42 output."""
    rt = _rt(runtime_root)
    path = Path(rt) / "state" / "runtime_operating_mode.json"
    data = _read_json(path)
    if data and data.get("operating_mode"):
        return str(data["operating_mode"])
    return "REPAIR_FOCUSED"


# ---------------------------------------------------------------------------
# Queue classification
# ---------------------------------------------------------------------------

def classify_queue_priority(package: dict[str, Any], operating_mode: str = "REPAIR_FOCUSED") -> str:
    """Return Q1..Q4 priority class for a decision package."""
    score = score_queue_entry(package, operating_mode)
    return classify_queue_priority_class(score)


def build_decision_queue(
    packages: list[dict[str, Any]],
    queue_state: dict[str, Any],
    operating_mode: str = "REPAIR_FOCUSED",
) -> list[dict[str, Any]]:
    """Merge packages with persisted queue state, score, classify, and sort.

    Returns list of enriched queue entries sorted by priority (Q1 first)
    then by score descending within each class.
    """
    enriched: list[dict[str, Any]] = []
    for pkg in packages:
        did = pkg.get("decision_id", "")
        persisted = queue_state.get(did, {})
        # Status from persisted state takes precedence; fall back to package status
        status = persisted.get("status") or pkg.get("status", "OPEN")

        # Compute score + class using current operating mode
        score = score_queue_entry(pkg, operating_mode)
        priority_class = classify_queue_priority_class(score)

        entry: dict[str, Any] = {
            **pkg,
            "status": status,
            "queue_score": score,
            "queue_priority_class": priority_class,
            "queue_priority_rank": queue_priority_rank(priority_class),
            "age_bucket": classify_age_bucket(pkg.get("ts", "")),
        }
        # Carry over any operator notes from persisted state
        if "operator_note" in persisted:
            entry["operator_note"] = persisted["operator_note"]
        if "deferred_until" in persisted:
            entry["deferred_until"] = persisted["deferred_until"]
        if "superseded_by" in persisted:
            entry["superseded_by"] = persisted["superseded_by"]
        enriched.append(entry)

    # Sort: priority rank ASC (Q1=1 is most urgent), then score DESC
    enriched.sort(key=lambda e: (e["queue_priority_rank"], -e["queue_score"]))
    return enriched


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------

def _transition(
    decision_id: str,
    new_status: str,
    operator_id: str,
    runtime_root: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generic lifecycle transition — validates, persists, appends audit log."""
    rt = _rt(runtime_root)
    state_path = Path(rt) / "state" / "decision_queue_state.json"
    log_path   = Path(rt) / "state" / "decision_queue_log.jsonl"

    state_data = _read_json(state_path) or {"entries": {}}
    entries: dict[str, Any] = state_data.get("entries", {})

    current_status = entries.get(decision_id, {}).get("status", "OPEN")

    if not valid_queue_status_transition(current_status, new_status):
        return {
            "ok": False,
            "reason": f"transition {current_status} → {new_status} not allowed",
            "decision_id": decision_id,
        }

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry: dict[str, Any] = {
        "status": new_status,
        "operator_id": operator_id,
        "ts": ts,
    }
    if extra:
        entry.update(extra)
    entries[decision_id] = entry

    state_data["entries"] = entries
    _atomic_write(state_path, state_data)

    # Append to audit log
    audit_row = {
        "ts": ts,
        "decision_id": decision_id,
        "old_status": current_status,
        "new_status": new_status,
        "operator_id": operator_id,
        **(extra or {}),
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(audit_row) + "\n")

    return {"ok": True, "decision_id": decision_id, "new_status": new_status, "ts": ts}


def defer_decision(
    decision_id: str,
    operator_id: str,
    reason: str = "",
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Transition decision to DEFERRED status."""
    return _transition(
        decision_id, "DEFERRED", operator_id, runtime_root,
        extra={"reason": reason} if reason else None,
    )


def reopen_decision(
    decision_id: str,
    operator_id: str,
    reason: str = "",
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Transition decision back to OPEN status."""
    return _transition(
        decision_id, "OPEN", operator_id, runtime_root,
        extra={"reason": reason} if reason else None,
    )


def supersede_decision(
    decision_id: str,
    operator_id: str,
    superseded_by: str,
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Mark decision as SUPERSEDED by a newer decision ID."""
    return _transition(
        decision_id, "SUPERSEDED", operator_id, runtime_root,
        extra={"superseded_by": superseded_by},
    )


def archive_decision(
    decision_id: str,
    operator_id: str,
    reason: str = "",
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Archive (terminal) a decision."""
    return _transition(
        decision_id, "ARCHIVED", operator_id, runtime_root,
        extra={"reason": reason} if reason else None,
    )


# ---------------------------------------------------------------------------
# Stale expiry
# ---------------------------------------------------------------------------

def expire_stale_decisions(
    queue_entries: list[dict[str, Any]],
    queue_state: dict[str, Any],
    runtime_root: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Auto-transition eligible OPEN decisions to STALE based on age policy.

    Returns (updated_entries, stale_count).
    Does NOT auto-archive — operator must still decide on STALE items.
    """
    stale_after     = STALE_DECISION_POLICY["stale_after_seconds"]
    critical_stale  = STALE_DECISION_POLICY["critical_stale_after_seconds"]
    now             = time.time()
    stale_count     = 0
    updated         = []

    rt = _rt(runtime_root)
    state_path = Path(rt) / "state" / "decision_queue_state.json"
    log_path   = Path(rt) / "state" / "decision_queue_log.jsonl"

    state_data = _read_json(state_path) or {"entries": {}}
    entries: dict[str, Any] = state_data.get("entries", {})

    for entry in queue_entries:
        did    = entry.get("decision_id", "")
        status = entry.get("status", "OPEN")

        if status != "OPEN":
            updated.append(entry)
            continue

        # Determine stale threshold for this entry
        priority = str(entry.get("priority", "MEDIUM")).upper()
        threshold = critical_stale if priority == "CRITICAL" else stale_after

        ts_raw = entry.get("ts", "")
        # Parse age
        if isinstance(ts_raw, str) and ts_raw:
            try:
                import time as _t
                age = now - _t.mktime(_t.strptime(ts_raw[:19], "%Y-%m-%dT%H:%M:%S"))
            except Exception:
                age = 0.0
        elif ts_raw:
            age = max(0.0, now - float(ts_raw))
        else:
            age = 0.0

        if age >= threshold:
            ts_now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            entries[did] = {"status": "STALE", "operator_id": "system", "ts": ts_now}
            audit_row = {
                "ts": ts_now,
                "decision_id": did,
                "old_status": "OPEN",
                "new_status": "STALE",
                "operator_id": "system",
                "reason": "auto-expired by stale policy",
            }
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(audit_row) + "\n")
            entry = {**entry, "status": "STALE"}
            stale_count += 1

        updated.append(entry)

    state_data["entries"] = entries
    _atomic_write(state_path, state_data)
    return updated, stale_count


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_decision_queue_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the full decision queue governance report."""
    rt = _rt(runtime_root)
    operating_mode  = load_operating_mode(rt)
    packages        = load_decision_packages(rt)
    queue_state     = load_queue_state(rt)

    queue = build_decision_queue(packages, queue_state, operating_mode)
    queue, stale_count = expire_stale_decisions(queue, queue_state, rt)

    # Partition by status
    open_entries      = [e for e in queue if e.get("status") == "OPEN"]
    deferred_entries  = [e for e in queue if e.get("status") == "DEFERRED"]
    stale_entries     = [e for e in queue if e.get("status") == "STALE"]

    # Q1 urgent count (open Q1 items)
    urgent_count = sum(1 for e in open_entries if e.get("queue_priority_class") == "Q1")

    # Type distribution
    type_dist: dict[str, int] = {}
    for e in open_entries:
        dt = e.get("decision_type", "UNKNOWN")
        type_dist[dt] = type_dist.get(dt, 0) + 1

    # Top decision (highest-scored open entry)
    top = open_entries[0] if open_entries else None

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":                    ts,
        "run_id":                str(uuid.uuid4()),
        "operating_mode":        operating_mode,
        "total_packages":        len(queue),
        "open_count":            len(open_entries),
        "deferred_count":        len(deferred_entries),
        "stale_count":           stale_count,
        "urgent_count":          urgent_count,
        "queue":                 queue,
        "type_distribution":     type_dist,
        "top_decision":          top,
        "operator_action_required": True,
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_decision_queue(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist the decision queue governance report to three outputs."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    ledger_path = state_dir / "decision_queue_governance_log.jsonl"
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    latest_path = state_dir / "decision_queue_governance_latest.json"
    _atomic_write(latest_path, report)

    # 3. Slim summary
    summary = {
        "ts":             report["ts"],
        "run_id":         report["run_id"],
        "operating_mode": report["operating_mode"],
        "open_count":     report["open_count"],
        "deferred_count": report["deferred_count"],
        "stale_count":    report["stale_count"],
        "urgent_count":   report["urgent_count"],
        "type_distribution": report["type_distribution"],
        "operator_action_required": True,
    }
    summary_path = state_dir / "decision_queue_summary.json"
    _atomic_write(summary_path, summary)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_decision_queue_governance(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-44 decision queue governance and persist outputs."""
    try:
        report = build_decision_queue_report(runtime_root)
        store_decision_queue(report, runtime_root)
        return {
            "ok":             True,
            "open_count":     report["open_count"],
            "deferred_count": report["deferred_count"],
            "stale_count":    report["stale_count"],
            "urgent_count":   report["urgent_count"],
            "operating_mode": report["operating_mode"],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
