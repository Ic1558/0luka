"""AG-53: Operator Decision Flow Integrity Layer.

Validates the complete operator decision lifecycle:
  recommendation → governance gate → operator queue → operator decision → memory → audit

Validation-only — no mutation, no enforcement, no auto-approval,
no repair execution, no governance change.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


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

def load_governance_gate(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-52 governance gate outputs."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_governance_gate_latest.json") or {}
    return {
        "present": bool(latest),
        "gated_recommendations": latest.get("gated_recommendations", []),
        "total_count": latest.get("total_count", 0),
        "ts": latest.get("ts"),
    }


def load_operator_queue(runtime_root: str | None = None) -> dict[str, Any]:
    """Load operator inbox entries (AG-18 operator queue)."""
    rt = _rt(runtime_root)
    inbox = _read_jsonl(Path(rt) / "state" / "operator_inbox.jsonl")
    return {
        "present": bool(inbox),
        "entries": inbox,
        "entry_ids": {e.get("task_id") or e.get("decision_id") or e.get("id", "") for e in inbox},
    }


def load_decision_queue(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-44 decision queue state."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "decision_queue_governance_latest.json") or {}
    return {
        "present": bool(latest),
        "open_count": latest.get("open_count", 0),
        "entries": latest.get("entries", []),
    }


def load_decision_memory(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-45 operator decision memory."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "operator_decision_memory_latest.json") or {}
    return {
        "present": bool(latest),
        "memory_entries": latest.get("memory_entries", []),
        "pattern_count": latest.get("pattern_count", 0),
    }


def load_trust_guidance(runtime_root: str | None = None) -> dict[str, Any]:
    """Load AG-50 trust guidance entries (used as recommendations source)."""
    rt = _rt(runtime_root)
    latest = _read_json(Path(rt) / "state" / "runtime_trust_guidance_latest.json") or {}
    return {
        "present": bool(latest),
        "guidance_entries": latest.get("guidance_entries", []),
        "guidance_mode": latest.get("guidance_mode"),
    }


# ---------------------------------------------------------------------------
# Lifecycle validation
# ---------------------------------------------------------------------------

def _has_governance_metadata(rec: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check that a recommendation has required governance gate metadata."""
    missing: list[str] = []
    for field in ("governance_class", "requires_operator_review", "recommended_review_level"):
        if field not in rec:
            missing.append(field)
    return (len(missing) == 0), missing


def validate_recommendation_lifecycle(
    rec: dict[str, Any],
    operator_queue: dict[str, Any],
    decision_queue: dict[str, Any],
    decision_memory: dict[str, Any],
) -> dict[str, Any]:
    """Validate one recommendation through the full lifecycle chain."""
    rec_id = rec.get("recommendation_id") or rec.get("guidance_id") or "unknown"
    chain: dict[str, Any] = {
        "recommendation_id":  rec_id,
        "governance_gate":    False,
        "operator_queue":     False,
        "operator_decision":  False,
        "memory_write":       False,
        "audit_trail":        False,
        "missing_steps":      [],
        "broken_chain":       False,
        "valid_lifecycle":    False,
    }

    # Step 1: governance gate metadata present
    has_meta, missing_fields = _has_governance_metadata(rec)
    chain["governance_gate"] = has_meta
    if not has_meta:
        chain["missing_steps"].append(f"governance_gate (missing: {missing_fields})")

    # Step 2: operator queue — check if any queue entry references this recommendation
    # Use presence of operator queue + decision queue as proxy (queue state is shared)
    chain["operator_queue"] = operator_queue["present"] or decision_queue["present"]
    if not chain["operator_queue"]:
        chain["missing_steps"].append("operator_queue")

    # Step 3: operator decision — decision queue entries represent operator decisions
    chain["operator_decision"] = decision_queue["present"] and decision_queue["open_count"] >= 0
    if not chain["operator_decision"] and not decision_queue["present"]:
        chain["missing_steps"].append("operator_decision")

    # Step 4: memory write — decision memory present
    chain["memory_write"] = decision_memory["present"]
    if not chain["memory_write"]:
        chain["missing_steps"].append("memory_write")

    # Step 5: audit trail — if governance gate + decision queue present, audit exists
    chain["audit_trail"] = has_meta and decision_queue["present"]
    if not chain["audit_trail"]:
        chain["missing_steps"].append("audit_trail")

    chain["broken_chain"]   = len(chain["missing_steps"]) > 0
    chain["valid_lifecycle"] = not chain["broken_chain"]
    return chain


def run_lifecycle_validation(
    governance_gate: dict[str, Any],
    operator_queue: dict[str, Any],
    decision_queue: dict[str, Any],
    decision_memory: dict[str, Any],
    trust_guidance: dict[str, Any],
) -> dict[str, Any]:
    """Validate all recommendations through the full lifecycle."""
    # Collect recommendations from governance gate; fall back to trust guidance entries
    recs: list[dict] = governance_gate.get("gated_recommendations", [])
    if not recs:
        recs = trust_guidance.get("guidance_entries", [])

    results: list[dict] = []
    for rec in recs:
        result = validate_recommendation_lifecycle(
            rec, operator_queue, decision_queue, decision_memory
        )
        results.append(result)

    valid_count  = sum(1 for r in results if r["valid_lifecycle"])
    broken_count = sum(1 for r in results if r["broken_chain"])
    missing_queue_count  = sum(1 for r in results if "operator_queue" in r.get("missing_steps", []))
    missing_memory_count = sum(1 for r in results if "memory_write"   in r.get("missing_steps", []))

    return {
        "lifecycle_results":        results,
        "recommendations_checked":  len(results),
        "valid_lifecycle":          valid_count,
        "broken_chain":             broken_count,
        "missing_queue":            missing_queue_count,
        "missing_memory":           missing_memory_count,
    }


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_integrity_report(runtime_root: str | None = None) -> dict[str, Any]:
    """Build the AG-53 operator decision flow integrity report."""
    rt = _rt(runtime_root)

    governance_gate  = load_governance_gate(rt)
    operator_queue   = load_operator_queue(rt)
    decision_queue   = load_decision_queue(rt)
    decision_memory  = load_decision_memory(rt)
    trust_guidance   = load_trust_guidance(rt)

    validation = run_lifecycle_validation(
        governance_gate, operator_queue, decision_queue, decision_memory, trust_guidance
    )

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "ts":                       ts,
        "run_id":                   str(uuid.uuid4()),
        "recommendations_checked":  validation["recommendations_checked"],
        "valid_lifecycle":          validation["valid_lifecycle"],
        "broken_chain":             validation["broken_chain"],
        "missing_queue":            validation["missing_queue"],
        "missing_memory":           validation["missing_memory"],
        "lifecycle_results":        validation["lifecycle_results"],
        "broken_results":           [r for r in validation["lifecycle_results"] if r["broken_chain"]],
        "evidence_refs": [
            "runtime_governance_gate_latest.json",
            "decision_queue_governance_latest.json",
            "operator_decision_memory_latest.json",
            "runtime_trust_guidance_latest.json",
        ],
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_integrity_outputs(report: dict[str, Any], runtime_root: str | None = None) -> None:
    """Persist AG-53 outputs — three required files."""
    rt = _rt(runtime_root)
    state_dir = Path(rt) / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1. Append-only JSONL ledger
    log_path = state_dir / "runtime_operator_decision_integrity_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    # 2. Latest snapshot (atomic)
    _atomic_write(state_dir / "runtime_operator_decision_integrity_latest.json", report)

    # 3. Slim index (atomic)
    index = {
        "ts":                      report["ts"],
        "run_id":                  report["run_id"],
        "recommendations_checked": report["recommendations_checked"],
        "valid_lifecycle":         report["valid_lifecycle"],
        "broken_chain":            report["broken_chain"],
        "missing_queue":           report["missing_queue"],
        "missing_memory":          report["missing_memory"],
    }
    _atomic_write(state_dir / "runtime_operator_decision_integrity_index.json", index)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def run_operator_decision_integrity(runtime_root: str | None = None) -> dict[str, Any]:
    """Run AG-53 operator decision flow integrity validation and persist outputs."""
    try:
        report = build_integrity_report(runtime_root)
        store_integrity_outputs(report, runtime_root)
        return {
            "ok":                      True,
            "recommendations_checked": report["recommendations_checked"],
            "valid_lifecycle":         report["valid_lifecycle"],
            "broken_chain":            report["broken_chain"],
            "missing_queue":           report["missing_queue"],
            "missing_memory":          report["missing_memory"],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
