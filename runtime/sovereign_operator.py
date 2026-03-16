"""AG-72: Sovereign Operator Mode — full control plane for the operator."""
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collect_runtime_state(sd: Path) -> dict:
    """Collect current state across all sovereign capabilities."""
    state: dict = {}

    # Chain execution
    p = sd / "runtime_chain_runner_latest.json"
    state["chain_execution"] = json.loads(p.read_text()) if p.exists() else None

    # Decision actions
    p = sd / "runtime_operator_decision_record_latest.json"
    state["decision_actions"] = json.loads(p.read_text()) if p.exists() else None

    # Policy review
    p = sd / "runtime_policy_workflow_latest.json"
    state["policy_review"] = json.loads(p.read_text()) if p.exists() else None

    # Anomaly handling
    anomaly: dict = {}
    pr = sd / "pattern_registry.json"
    if pr.exists():
        try:
            anomaly["patterns"] = json.loads(pr.read_text())
        except Exception:
            anomaly["patterns"] = []
    state["anomaly_handling"] = anomaly

    # Replay
    p = sd / "runtime_replay_latest.json"
    state["replay"] = json.loads(p.read_text()) if p.exists() else None

    # Self-audit view
    p = sd / "runtime_system_self_audit_latest.json"
    state["self_audit_view"] = json.loads(p.read_text()) if p.exists() else None

    # Governed inference
    p = sd / "runtime_governed_inference_latest.json"
    state["governed_inference"] = json.loads(p.read_text()) if p.exists() else None

    return state


def enter_sovereign_mode(operator_id: str) -> dict:
    """Enter sovereign operator mode — returns full control plane snapshot."""
    from runtime.sovereign_operator_policy import SOVEREIGN_CAPABILITIES, SOVEREIGN_VERSION, REQUIRE_OPERATOR_ID

    if REQUIRE_OPERATOR_ID and not operator_id:
        return {"ok": False, "error": "operator_id_required"}

    sd = _state_dir()
    session_id = str(uuid.uuid4())

    runtime_state = _collect_runtime_state(sd)

    session = {
        "session_id": session_id,
        "operator_id": operator_id,
        "version": SOVEREIGN_VERSION,
        "capabilities": SOVEREIGN_CAPABILITIES,
        "runtime_state": runtime_state,
        "mode": "SOVEREIGN",
        "ts_entered": _now(),
    }

    _atomic_write(sd / "runtime_sovereign_operator_latest.json", session)
    _append_jsonl(sd / "runtime_sovereign_operator_log.jsonl", session)

    idx_path = sd / "runtime_sovereign_operator_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({
        "session_id": session_id,
        "operator_id": operator_id,
        "ts_entered": session["ts_entered"],
    })
    _atomic_write(idx_path, idx)

    return session


def get_sovereign_latest() -> dict | None:
    sd = _state_dir()
    p = sd / "runtime_sovereign_operator_latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def list_sovereign_sessions() -> list:
    sd = _state_dir()
    p = sd / "runtime_sovereign_operator_index.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []
