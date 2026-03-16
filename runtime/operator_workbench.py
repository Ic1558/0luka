"""AG-68: Operator Workbench — aggregates runtime panels for operator use."""
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


def _load_panel_pending_queues(sd: Path) -> dict:
    """Aggregate pending items from known queue files."""
    queues: dict = {}
    for fname in [
        "runtime_chain_runner_index.json",
        "runtime_recommendation_state_index.json",
        "runtime_operator_decision_record_index.json",
    ]:
        p = sd / fname
        if p.exists():
            try:
                data = json.loads(p.read_text())
                queues[fname] = len(data) if isinstance(data, list) else 1
            except Exception:
                queues[fname] = 0
        else:
            queues[fname] = 0
    return queues


def _load_panel_policy_review(sd: Path) -> dict:
    """Aggregate latest policy workflow and bridge status."""
    result: dict = {}
    for fname, key in [
        ("runtime_policy_workflow_latest.json", "policy_workflow"),
        ("runtime_learning_policy_bridge_latest.json", "learning_bridge"),
    ]:
        p = sd / fname
        if p.exists():
            try:
                result[key] = json.loads(p.read_text())
            except Exception:
                result[key] = None
        else:
            result[key] = None
    return result


def _load_panel_recommendations(sd: Path) -> dict:
    """Latest recommendation state and trace counts."""
    result: dict = {}
    for fname, key in [
        ("runtime_recommendation_state_latest.json", "state_latest"),
        ("runtime_recommendation_trace_latest.json", "trace_latest"),
    ]:
        p = sd / fname
        if p.exists():
            try:
                result[key] = json.loads(p.read_text())
            except Exception:
                result[key] = None
        else:
            result[key] = None
    return result


def _load_panel_outcome_actions(sd: Path) -> dict:
    """Latest outcome governance record."""
    p = sd / "policy_outcome_latest.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


def _load_panel_anomaly_review(sd: Path) -> dict:
    """Pattern registry and policy candidate summary."""
    result: dict = {}
    p = sd / "pattern_registry.json"
    if p.exists():
        try:
            patterns = json.loads(p.read_text())
            result["pattern_count"] = len(patterns) if isinstance(patterns, list) else 0
        except Exception:
            result["pattern_count"] = 0
    else:
        result["pattern_count"] = 0

    cands: list = []
    cp = sd / "policy_candidates.jsonl"
    if cp.exists():
        try:
            cands = [json.loads(l) for l in cp.read_text().splitlines() if l.strip()]
        except Exception:
            pass
    result["candidate_count"] = len(cands)
    return result


def _load_panel_self_audit(sd: Path) -> dict:
    """Latest self-audit verdict."""
    p = sd / "runtime_system_self_audit_latest.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


def build_workbench(operator_id: str = "system") -> dict:
    """Build a full operator workbench snapshot."""
    from runtime.operator_workbench_policy import WORKBENCH_PANELS, WORKBENCH_VERSION

    sd = _state_dir()
    workbench_id = str(uuid.uuid4())

    panels = {
        "pending_queues": _load_panel_pending_queues(sd),
        "policy_review_board": _load_panel_policy_review(sd),
        "recommendation_board": _load_panel_recommendations(sd),
        "outcome_actions": _load_panel_outcome_actions(sd),
        "anomaly_review": _load_panel_anomaly_review(sd),
        "self_audit_panel": _load_panel_self_audit(sd),
    }

    snapshot = {
        "workbench_id": workbench_id,
        "operator_id": operator_id,
        "version": WORKBENCH_VERSION,
        "panels": panels,
        "panel_names": WORKBENCH_PANELS,
        "ts_built": _now(),
    }

    _atomic_write(sd / "runtime_operator_workbench_latest.json", snapshot)
    _append_jsonl(sd / "runtime_operator_workbench_log.jsonl", snapshot)

    idx_path = sd / "runtime_operator_workbench_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({
        "workbench_id": workbench_id,
        "operator_id": operator_id,
        "ts_built": snapshot["ts_built"],
    })
    _atomic_write(idx_path, idx)

    return snapshot


def get_workbench_latest() -> dict | None:
    sd = _state_dir()
    p = sd / "runtime_operator_workbench_latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def list_workbench_snapshots() -> list:
    sd = _state_dir()
    p = sd / "runtime_operator_workbench_index.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []
