"""AG-67: Learning-to-Policy Bridge."""
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timezone
from pathlib import Path


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _atomic_write(path: Path, data) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")

def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_bridge() -> list:
    """Bridge anomaly/pattern outputs into governance-ready policy candidates."""
    from runtime.learning_policy_bridge_policy import score_readiness

    try:
        from learning.pattern_extractor import update_pattern_registry
        patterns = update_pattern_registry()
    except Exception:
        patterns = []

    try:
        from learning.policy_candidates import generate_policy_candidates
        candidates = generate_policy_candidates()
    except Exception:
        candidates = []

    bridge_id = str(uuid.uuid4())
    bridge_records = []

    for candidate in candidates:
        candidate_id = candidate.get("candidate_id", str(uuid.uuid4()))
        confidence = float(candidate.get("confidence", 0.0))
        pattern_id = candidate.get("pattern_id")
        matched = next((p for p in patterns if p.get("pattern_id") == pattern_id), None)
        if not matched and patterns:
            matched = patterns[0]

        record = {
            "bridge_id": bridge_id,
            "record_id": str(uuid.uuid4()),
            "pattern_id": matched.get("pattern_id") if matched else None,
            "candidate_id": candidate_id,
            "candidate_confidence": confidence,
            "promotion_readiness": score_readiness(confidence),
            "provenance": {
                "pattern_type": matched.get("pattern_type") if matched else None,
                "candidate_suggestion": candidate.get("suggested_rule", ""),
            },
            "linked_policy_id": None,
            "ts_evaluated": _now(),
        }
        bridge_records.append(record)

    sd = _state_dir()
    report = {
        "bridge_id": bridge_id,
        "records": bridge_records,
        "pattern_count": len(patterns),
        "candidate_count": len(candidates),
        "ts_evaluated": _now(),
    }
    _atomic_write(sd / "runtime_learning_policy_bridge_latest.json", report)
    _append_jsonl(sd / "runtime_learning_policy_bridge_log.jsonl", report)

    idx_path = sd / "runtime_learning_policy_bridge_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({"bridge_id": bridge_id, "record_count": len(bridge_records), "ts_evaluated": report["ts_evaluated"]})
    _atomic_write(idx_path, idx)

    return bridge_records


def get_bridge(bridge_id: str) -> dict | None:
    sd = _state_dir()
    return next((r for r in _read_jsonl(sd / "runtime_learning_policy_bridge_log.jsonl")
                 if r.get("bridge_id") == bridge_id), None)


def list_bridges() -> list:
    sd = _state_dir()
    idx = sd / "runtime_learning_policy_bridge_index.json"
    if not idx.exists():
        return []
    try:
        return json.loads(idx.read_text())
    except Exception:
        return []
