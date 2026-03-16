"""AG-69: Headless Runtime Supervisor — persistent boot-safe supervisor state."""
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


def _check_service(service_name: str, sd: Path) -> dict:
    """Check a named service by probing its latest heartbeat/state file."""
    probe_files = {
        "mcs": sd / "runtime_operator_workbench_latest.json",
        "chain_runner": sd / "runtime_chain_runner_latest.json",
    }
    status = "UNKNOWN"
    last_seen: str | None = None

    probe = probe_files.get(service_name)
    if probe and probe.exists():
        try:
            data = json.loads(probe.read_text())
            ts = data.get("ts_built") or data.get("ts_evaluated") or data.get("ts")
            if ts:
                last_seen = ts
                status = "ALIVE"
        except Exception:
            status = "ERROR"
    else:
        status = "ABSENT"

    return {
        "service": service_name,
        "status": status,
        "last_seen": last_seen,
    }


def run_supervisor_check(operator_id: str = "system") -> dict:
    """Run a full supervisor health check across watched services."""
    from runtime.headless_supervisor_policy import WATCHED_SERVICES, SUPERVISOR_VERSION

    sd = _state_dir()
    check_id = str(uuid.uuid4())

    service_statuses = [_check_service(svc, sd) for svc in WATCHED_SERVICES]
    all_alive = all(s["status"] == "ALIVE" for s in service_statuses)

    report = {
        "check_id": check_id,
        "operator_id": operator_id,
        "version": SUPERVISOR_VERSION,
        "services": service_statuses,
        "overall_status": "HEALTHY" if all_alive else "DEGRADED",
        "ts_checked": _now(),
    }

    _atomic_write(sd / "runtime_headless_supervisor_latest.json", report)
    _append_jsonl(sd / "runtime_headless_supervisor_log.jsonl", report)

    idx_path = sd / "runtime_headless_supervisor_index.json"
    try:
        idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    except Exception:
        idx = []
    idx.append({
        "check_id": check_id,
        "overall_status": report["overall_status"],
        "ts_checked": report["ts_checked"],
    })
    _atomic_write(idx_path, idx)

    return report


def get_supervisor_latest() -> dict | None:
    sd = _state_dir()
    p = sd / "runtime_headless_supervisor_latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def list_supervisor_checks() -> list:
    sd = _state_dir()
    p = sd / "runtime_headless_supervisor_index.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []
