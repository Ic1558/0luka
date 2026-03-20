"""AG-66: Policy Promotion Workflow Hardening."""
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timezone
from pathlib import Path


def _state_dir():
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
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


def _run_stage(stage_name: str, fn) -> dict:
    ts_s = _now()
    try:
        result = fn()
        return {"stage_name": stage_name, "status": "PASS",
                "result_summary": str(result)[:200], "ts": ts_s}
    except Exception as e:
        return {"stage_name": stage_name, "status": "FAIL",
                "result_summary": str(e)[:200], "ts": ts_s}


def run_review(policy_id: str, operator_id: str) -> dict:
    """Run full policy promotion workflow review."""
    workflow_id = str(uuid.uuid4())
    ts_started = _now()
    sd = _state_dir()
    stages = []

    # Stage 1: candidate_check
    def _candidate_check():
        cands = _read_jsonl(sd / "policy_candidates.jsonl")
        matched = [c for c in cands if c.get("policy_id") == policy_id or c.get("candidate_id")]
        return f"candidates_found={len(matched)}"
    stages.append(_run_stage("candidate_check", _candidate_check))

    # Stage 2: promotion_check — fail-closed: raises on load failure or empty policy set
    def _promotion_check():
        from core.policy.policy_lifecycle import list_active_policies
        active = list_active_policies()
        if not active:
            raise RuntimeError("promotion_check_failed: policy set empty or unreadable")
        matched = [p for p in active if p.get("policy_id") == policy_id]
        return f"active_matched={len(matched)}"
    stages.append(_run_stage("promotion_check", _promotion_check))

    # Stage 3: effectiveness_check
    effectiveness_verdict = "UNKNOWN"
    def _effectiveness_check():
        nonlocal effectiveness_verdict
        from core.policy.effectiveness_store import run_and_persist
        result = run_and_persist(policy_id)
        effectiveness_verdict = result.get("verdict", "UNKNOWN")
        return f"verdict={effectiveness_verdict}"
    stages.append(_run_stage("effectiveness_check", _effectiveness_check))

    # Stage 4: outcome_governance
    def _outcome_governance():
        from core.policy.outcome_store import create_governance_record
        rec = create_governance_record({"verdict": effectiveness_verdict, "policy_id": policy_id})
        return f"governance_id={rec.get('governance_id','?')}"
    stages.append(_run_stage("outcome_governance", _outcome_governance))

    stages.append({"stage_name": "COMPLETE", "status": "PASS",
                   "result_summary": "workflow complete", "ts": _now()})

    overall_status = "PASS" if all(s["status"] == "PASS" for s in stages) else "FAIL"

    report = {
        "workflow_id": workflow_id,
        "policy_id": policy_id,
        "operator_id": operator_id,
        "stages": stages,
        "overall_status": overall_status,
        "ts_started": ts_started,
        "ts_finished": _now(),
    }

    _atomic_write(sd / "runtime_policy_workflow_latest.json", report)
    _append_jsonl(sd / "runtime_policy_workflow_log.jsonl", report)

    idx_path = sd / "runtime_policy_workflow_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({"workflow_id": workflow_id, "policy_id": policy_id,
                "overall_status": overall_status, "ts_started": ts_started})
    _atomic_write(idx_path, idx)

    return report


def get_workflow(workflow_id: str) -> dict | None:
    sd = _state_dir()
    return next((r for r in _read_jsonl(sd / "runtime_policy_workflow_log.jsonl")
                 if r.get("workflow_id") == workflow_id), None)


def list_workflows() -> list:
    sd = _state_dir()
    idx = sd / "runtime_policy_workflow_index.json"
    if not idx.exists():
        return []
    try:
        return json.loads(idx.read_text())
    except Exception:
        return []
