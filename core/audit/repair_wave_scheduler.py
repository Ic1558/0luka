"""AG-39: Supervised Repair Wave Scheduler.

Converts the AG-38 priority queue into operator-governed repair waves.

Wave lifecycle:
  PROPOSED → (operator approve/reject) → APPROVED → READY_FOR_EXECUTION
  APPROVED waves are handed off to AG-34 for supervised execution.

Invariants:
  - scheduling-only: never executes repairs, closes findings, or modifies governance state
  - never modifies audit_baseline, drift_finding_status, or drift_governance_log
  - all wave items are advisory; operator approve/reject gates every wave
  - deterministic given the same priority queue + policy
  - P1 items are always batched first
  - no target overlap within a wave (configurable)
  - unstable/degraded runtime → smaller wave sizes

Runtime outputs:
  $LUKA_RUNTIME_ROOT/state/repair_wave_schedule.json  — atomic overwrite (current schedule)
  $LUKA_RUNTIME_ROOT/state/repair_wave_log.jsonl      — append-only event log
  $LUKA_RUNTIME_ROOT/state/repair_wave_latest.json    — atomic overwrite (latest run summary)

Public API:
  run_repair_wave_scheduling(runtime_root=None) -> dict
  approve_repair_wave(wave_id, operator_id, runtime_root=None) -> dict
  reject_repair_wave(wave_id, operator_id, reason, runtime_root=None) -> dict
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from core.audit.wave_policy import (
    DEFAULT_WAVE_POLICY,
    can_items_share_wave,
    classify_wave_priority_bucket,
    max_wave_size_for_stability,
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


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _new_wave_id() -> str:
    return "wave-" + uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Source readers
# ---------------------------------------------------------------------------

def load_priority_queue(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Load AG-38 priority queue items."""
    state_d = _state_dir(runtime_root)
    data = _read_json(state_d / "repair_priority_queue.json")
    if data is None:
        return []
    return data.get("queue", [])


def load_stability_classification(runtime_root: str | None = None) -> str:
    """Load AG-37 stability classification. Defaults to STABLE if unavailable."""
    state_d = _state_dir(runtime_root)
    data = _read_json(state_d / "runtime_stability_score.json")
    if data is None:
        return "STABLE"
    return str(data.get("classification", "STABLE"))


def load_existing_wave_schedule(runtime_root: str | None = None) -> dict[str, Any]:
    """Load current wave schedule (for wave state transitions)."""
    state_d = _state_dir(runtime_root)
    data = _read_json(state_d / "repair_wave_schedule.json")
    return data or {"waves": []}


# ---------------------------------------------------------------------------
# Eligibility classification
# ---------------------------------------------------------------------------

def classify_wave_eligibility(
    item: dict[str, Any],
    existing_wave_items: list[dict[str, Any]],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Determine if a priority queue item is eligible for wave scheduling.

    Verdicts: ELIGIBLE | DEFER | BLOCK | ESCALATE

    BLOCK conditions:
      - item has no finding_id
      - target overlap with existing wave (when allow_target_overlap=False)

    ESCALATE conditions:
      - priority_class is None or unknown

    DEFER conditions:
      - wave slot is full (handled at build level, not here)
    """
    p = policy or DEFAULT_WAVE_POLICY

    fid = str(item.get("finding_id") or "").strip()
    if not fid or fid == "unknown":
        return {"verdict": "BLOCK", "reason": "missing finding_id"}

    pclass = str(item.get("priority_class") or "").upper()
    if pclass not in ("P1", "P2", "P3", "P4"):
        return {"verdict": "ESCALATE", "reason": f"unknown priority_class: {pclass!r}"}

    if not p.get("allow_target_overlap", False):
        for existing in existing_wave_items:
            if not can_items_share_wave(item, existing, p):
                return {
                    "verdict": "BLOCK",
                    "reason": f"target overlap with finding_id={existing.get('finding_id')!r}",
                }

    return {"verdict": "ELIGIBLE", "reason": "ok"}


# ---------------------------------------------------------------------------
# Wave builder
# ---------------------------------------------------------------------------

def build_repair_waves(
    queue_items: list[dict[str, Any]],
    stability_classification: str = "STABLE",
    policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic, ordered repair waves from a priority queue.

    Rules:
      - P1 items are always placed in earlier waves
      - max wave size governed by stability classification
      - no target overlap within a wave (when policy.allow_target_overlap=False)
      - items that cannot fit in any wave are marked DEFER

    Returns a list of wave dicts, each with:
      wave_id, wave_number, status, items, item_count, priority_classes_present, ts_created
    """
    p = policy or DEFAULT_WAVE_POLICY
    max_per_wave = max_wave_size_for_stability(stability_classification, p)
    max_waves = int(p.get("max_waves_per_run", 10))
    p1_first = bool(p.get("p1_first", True))

    # Sort by bucket order then priority_score desc, then finding_id for determinism
    sorted_items = sorted(
        queue_items,
        key=lambda x: (
            classify_wave_priority_bucket(x.get("priority_class", "P4")),
            -int(x.get("priority_score", 0)),
            str(x.get("finding_id", "")),
        ),
    )

    waves: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    unassigned = list(sorted_items)

    wave_number = 1
    while unassigned and wave_number <= max_waves:
        wave_items: list[dict[str, Any]] = []
        still_unassigned: list[dict[str, Any]] = []

        for item in unassigned:
            if len(wave_items) >= max_per_wave:
                still_unassigned.append(item)
                continue

            eligibility = classify_wave_eligibility(item, wave_items, p)
            if eligibility["verdict"] == "ELIGIBLE":
                wave_items.append(item)
            elif eligibility["verdict"] == "BLOCK":
                still_unassigned.append(item)
            elif eligibility["verdict"] == "ESCALATE":
                still_unassigned.append(item)
            else:  # DEFER
                deferred.append({**item, "_wave_verdict": "DEFER",
                                  "_wave_reason": eligibility["reason"]})

        if not wave_items:
            # No progress possible — remaining items cannot be placed
            deferred.extend(still_unassigned)
            break

        priority_classes = sorted({i.get("priority_class", "P4") for i in wave_items},
                                   key=lambda c: classify_wave_priority_bucket(c))
        waves.append({
            "wave_id": _new_wave_id(),
            "wave_number": wave_number,
            "status": "PROPOSED",
            "items": wave_items,
            "item_count": len(wave_items),
            "priority_classes_present": priority_classes,
            "ts_created": _now(),
            "operator_action_required": True,
        })
        unassigned = still_unassigned
        wave_number += 1

    # Any items still unassigned beyond max_waves → deferred
    deferred.extend(unassigned)

    return waves, deferred


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_wave_schedule(
    waves: list[dict[str, Any]],
    deferred: list[dict[str, Any]],
    summary: dict[str, Any],
    runtime_root: str | None = None,
) -> None:
    """Write AG-39 outputs: schedule JSON (atomic), append log, atomic latest."""
    state_d = _state_dir(runtime_root)

    # 1. Atomic schedule snapshot
    _atomic_write(state_d / "repair_wave_schedule.json", {
        "ts": _now(),
        "total_waves": len(waves),
        "total_items": sum(w["item_count"] for w in waves),
        "deferred_items": len(deferred),
        "waves": waves,
        "deferred": deferred,
    })

    # 2. Append to wave log
    log_path = state_d / "repair_wave_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")

    # 3. Atomic latest
    _atomic_write(state_d / "repair_wave_latest.json", summary)


def _find_wave(schedule: dict[str, Any], wave_id: str) -> dict[str, Any] | None:
    """Find a wave by ID in a schedule dict."""
    for wave in schedule.get("waves", []):
        if wave.get("wave_id") == wave_id:
            return wave
    return None


# ---------------------------------------------------------------------------
# Wave state transitions (operator-gated)
# ---------------------------------------------------------------------------

def approve_repair_wave(
    wave_id: str,
    operator_id: str,
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Operator approves a PROPOSED wave → APPROVED → READY_FOR_EXECUTION.

    Does not execute anything. Updates schedule JSON and appends to log.
    """
    state_d = _state_dir(runtime_root)
    schedule = _read_json(state_d / "repair_wave_schedule.json")
    if schedule is None:
        return {"ok": False, "error": "no wave schedule found"}

    wave = _find_wave(schedule, wave_id)
    if wave is None:
        return {"ok": False, "error": f"wave_id {wave_id!r} not found"}

    if wave["status"] != "PROPOSED":
        return {
            "ok": False,
            "error": f"wave {wave_id!r} is {wave['status']!r} — can only approve PROPOSED waves",
        }

    wave["status"] = "APPROVED"
    wave["ts_approved"] = _now()
    wave["approved_by"] = operator_id

    _atomic_write(state_d / "repair_wave_schedule.json", schedule)

    event = {
        "event": "wave_approved",
        "wave_id": wave_id,
        "operator_id": operator_id,
        "ts": _now(),
    }
    log_path = state_d / "repair_wave_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")

    return {"ok": True, "wave_id": wave_id, "new_status": "APPROVED"}


def reject_repair_wave(
    wave_id: str,
    operator_id: str,
    reason: str = "",
    runtime_root: str | None = None,
) -> dict[str, Any]:
    """Operator rejects a PROPOSED wave → REJECTED.

    Does not execute anything. Updates schedule JSON and appends to log.
    """
    state_d = _state_dir(runtime_root)
    schedule = _read_json(state_d / "repair_wave_schedule.json")
    if schedule is None:
        return {"ok": False, "error": "no wave schedule found"}

    wave = _find_wave(schedule, wave_id)
    if wave is None:
        return {"ok": False, "error": f"wave_id {wave_id!r} not found"}

    if wave["status"] != "PROPOSED":
        return {
            "ok": False,
            "error": f"wave {wave_id!r} is {wave['status']!r} — can only reject PROPOSED waves",
        }

    wave["status"] = "REJECTED"
    wave["ts_rejected"] = _now()
    wave["rejected_by"] = operator_id
    wave["rejection_reason"] = reason

    _atomic_write(state_d / "repair_wave_schedule.json", schedule)

    event = {
        "event": "wave_rejected",
        "wave_id": wave_id,
        "operator_id": operator_id,
        "reason": reason,
        "ts": _now(),
    }
    log_path = state_d / "repair_wave_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")

    return {"ok": True, "wave_id": wave_id, "new_status": "REJECTED"}


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_repair_wave_scheduling(
    runtime_root: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the full AG-39 repair wave scheduling.

    Steps:
      1. Load AG-38 priority queue
      2. Load AG-37 stability classification
      3. Apply wave policy to build ordered waves
      4. Store outputs
      5. Return summary

    Never modifies governance state, baseline, findings, or repair artifacts.
    All waves are PROPOSED — operator must approve/reject each wave.
    """
    p = policy or DEFAULT_WAVE_POLICY

    queue_items = load_priority_queue(runtime_root)
    stability_classification = load_stability_classification(runtime_root)
    max_per_wave = max_wave_size_for_stability(stability_classification, p)

    waves, deferred = build_repair_waves(queue_items, stability_classification, p)

    proposed_count = sum(1 for w in waves if w["status"] == "PROPOSED")
    total_items = sum(w["item_count"] for w in waves)
    p1_waves = [w for w in waves if "P1" in w.get("priority_classes_present", [])]

    summary: dict[str, Any] = {
        "ts": _now(),
        "run_id": "wave-sched-" + uuid.uuid4().hex[:8],
        "total_waves": len(waves),
        "proposed_count": proposed_count,
        "total_items_scheduled": total_items,
        "deferred_items": len(deferred),
        "stability_classification": stability_classification,
        "max_per_wave": max_per_wave,
        "p1_wave_count": len(p1_waves),
        "first_wave_id": waves[0]["wave_id"] if waves else None,
    }

    try:
        store_wave_schedule(waves, deferred, summary, runtime_root)
    except Exception as exc:
        summary["storage_error"] = str(exc)

    return {
        "ok": True,
        "run_id": summary["run_id"],
        "total_waves": len(waves),
        "total_items_scheduled": total_items,
        "deferred_items": len(deferred),
        "stability_classification": stability_classification,
        "p1_wave_count": len(p1_waves),
        "first_wave_id": summary["first_wave_id"],
    }
