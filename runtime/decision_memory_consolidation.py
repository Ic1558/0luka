"""AG-62: Decision Memory Consolidation Layer."""
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timezone
from pathlib import Path


def _state_dir():
    rt = os.environ.get("LUKA_RUNTIME_ROOT", str(Path.home() / "0luka_runtime"))
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _atomic_write(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

def _append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")

def _read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

def _now():
    return datetime.now(timezone.utc).isoformat()


def consolidate(trace_id: str) -> dict:
    """Consolidate all decision-related memory for a trace_id."""
    sources = []

    # Read operator decisions for this trace_id
    sd = _state_dir()
    decisions = _read_jsonl(sd / "runtime_operator_decision_record_log.jsonl")
    dec_ids = []
    for d in decisions:
        if d.get("trace_id") == trace_id:
            sources.append({"source_type": "operator_decision", "source_id": d.get("decision_record_id")})
            dec_ids.append(d.get("decision_record_id"))

    # Read recommendation trace for this trace_id
    traces = _read_jsonl(sd / "runtime_recommendation_trace_log.jsonl")
    rec_ids = []
    gov_ids = []
    for t in traces:
        if t.get("trace_id") == trace_id:
            sources.append({"source_type": "recommendation_trace", "source_id": t.get("recommendation_id")})
            rec_ids.append(t.get("recommendation_id"))
            if t.get("governance_id"):
                gov_ids.append(t.get("governance_id"))

    # Read policy outcomes (governance log) - check for matching governance_ids
    gov_log = _read_jsonl(sd / "policy_outcome_governance.jsonl")
    pol_ids = []
    for g in gov_log:
        if g.get("governance_id") in gov_ids:
            sources.append({"source_type": "policy_outcome", "source_id": g.get("governance_id")})
            if g.get("policy_id"):
                pol_ids.append(g.get("policy_id"))

    record = {
        "memory_id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "sources": sources,
        "consolidated_at": _now(),
        "recommendation_ids": list(set(rec_ids)),
        "decision_ids": list(set(dec_ids)),
        "governance_ids": list(set(gov_ids)),
        "policy_ids": list(set(pol_ids)),
    }

    _atomic_write(sd / "runtime_decision_memory_latest.json", record)
    _append_jsonl(sd / "runtime_decision_memory_log.jsonl", record)

    idx_path = sd / "runtime_decision_memory_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({"memory_id": record["memory_id"], "trace_id": trace_id, "consolidated_at": record["consolidated_at"]})
    _atomic_write(idx_path, idx)

    return record


def get_memory(trace_id: str) -> dict | None:
    sd = _state_dir()
    recs = _read_jsonl(sd / "runtime_decision_memory_log.jsonl")
    return next((r for r in reversed(recs) if r.get("trace_id") == trace_id), None)


def list_memories() -> list:
    sd = _state_dir()
    idx = sd / "runtime_decision_memory_index.json"
    if not idx.exists():
        return []
    try:
        return json.loads(idx.read_text())
    except Exception:
        return []
