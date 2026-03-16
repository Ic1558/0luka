"""AG-71: Multi-Agent Execution Contract — canonical task/result schema enforcement."""
from __future__ import annotations
import json, os, uuid
from datetime import datetime, timezone
from pathlib import Path


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
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


def validate_task(task: dict) -> tuple[bool, str]:
    """Validate a task against the multi-agent contract schema."""
    from runtime.multi_agent_contract_policy import REQUIRED_TASK_FIELDS, AUTHORITY_LEVELS
    for field in REQUIRED_TASK_FIELDS:
        if field not in task:
            return False, f"missing_field:{field}"
    if task.get("authority_level") not in AUTHORITY_LEVELS:
        return False, f"invalid_authority_level:{task.get('authority_level')}"
    return True, "ok"


def validate_result(result: dict) -> tuple[bool, str]:
    """Validate a result against the multi-agent contract schema."""
    from runtime.multi_agent_contract_policy import REQUIRED_RESULT_FIELDS, ALLOWED_STATUSES
    for field in REQUIRED_RESULT_FIELDS:
        if field not in result:
            return False, f"missing_field:{field}"
    if result.get("status") not in ALLOWED_STATUSES:
        return False, f"invalid_status:{result.get('status')}"
    return True, "ok"


def register_contract_task(task: dict) -> dict:
    """Register a task under the multi-agent contract."""
    valid, reason = validate_task(task)
    contract_id = str(uuid.uuid4())
    record = {
        "contract_id": contract_id,
        "task_id": task.get("task_id"),
        "actor_id": task.get("actor_id"),
        "authority_level": task.get("authority_level"),
        "trace_id": task.get("trace_id"),
        "valid": valid,
        "validation_reason": reason,
        "task": task,
        "ts_registered": _now(),
    }
    sd = _state_dir()
    _atomic_write(sd / "runtime_multi_agent_contract_latest.json", record)
    _append_jsonl(sd / "runtime_multi_agent_contract_log.jsonl", record)

    idx_path = sd / "runtime_multi_agent_contract_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({"contract_id": contract_id, "task_id": task.get("task_id"), "valid": valid, "ts_registered": record["ts_registered"]})
    _atomic_write(idx_path, idx)

    return record


def get_contract_latest() -> dict | None:
    sd = _state_dir()
    p = sd / "runtime_multi_agent_contract_latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def list_contracts() -> list:
    sd = _state_dir()
    p = sd / "runtime_multi_agent_contract_index.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []
