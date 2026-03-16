"""AG-69: Headless Runtime Supervisor — persistent boot-safe supervisor state."""
from __future__ import annotations
import json, os, subprocess, time, uuid
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


def _pid_alive(pid: int) -> bool:
    """Return True if pid is a live process (stdlib only, no psutil).

    Uses waitpid(WNOHANG) for child processes to correctly handle zombies on
    macOS/BSD. Falls back to os.kill(pid, 0) for non-child pids.
    """
    try:
        waited_pid, _ = os.waitpid(pid, os.WNOHANG)
        return waited_pid == 0  # 0 = still running; non-0 = exited (reaped)
    except ChildProcessError:
        pass  # not our child — fall through to kill probe
    except Exception:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _write_pid(sd: Path, pid: int) -> None:
    _atomic_write(sd / "supervisor_managed_pid.json", {"pid": pid, "ts_started": _now()})


def _read_pid(sd: Path) -> int | None:
    p = sd / "supervisor_managed_pid.json"
    if not p.exists():
        return None
    try:
        return int(json.loads(p.read_text())["pid"])
    except Exception:
        return None


def _read_continuity_state(sd: Path) -> dict:
    """Read key markers from persisted runtime state for continuity evidence."""
    p = sd / "runtime_self_awareness_latest.json"
    if not p.exists():
        return {"runtime_self_awareness": None}
    try:
        data = json.loads(p.read_text())
        return {
            "runtime_self_awareness": {
                "ts": data.get("ts"),
                "run_id": data.get("run_id"),
                "readiness": (data.get("readiness") or {}).get("readiness"),
            }
        }
    except Exception:
        return {"runtime_self_awareness": None}


def _record_event(sd: Path, event: str, detail: dict) -> None:
    _append_jsonl(sd / "supervisor_events.jsonl", {"ts": _now(), "event": event, **detail})


def start_supervised_process(command: list, sd: Path) -> int:
    """Start subprocess, record PID. Returns PID."""
    proc = subprocess.Popen(command, start_new_session=True)
    _write_pid(sd, proc.pid)
    return proc.pid


def supervise_once(
    command: list,
    *,
    restart_count: int = 0,
    max_restarts: int = 3,
) -> dict:
    """One supervision tick: check liveness, restart if dead, enforce restart limit."""
    sd = _state_dir()
    pid = _read_pid(sd)

    if pid is None:
        return {"action": "no_pid", "restart_count": restart_count}

    if _pid_alive(pid):
        return {"action": "alive", "pid": pid, "restart_count": restart_count}

    # Process dead
    _record_event(sd, "process_dead", {"pid": pid, "restart_count": restart_count})

    if restart_count >= max_restarts:
        _record_event(sd, "restart_limit_reached", {"max_restarts": max_restarts})
        return {
            "action": "restart_limit_reached",
            "pid": pid,
            "restart_count": restart_count,
            "max_restarts": max_restarts,
        }

    continuity = _read_continuity_state(sd)
    new_pid = start_supervised_process(command, sd)
    _record_event(sd, "process_restarted", {
        "old_pid": pid, "new_pid": new_pid,
        "restart_count": restart_count + 1,
        "continuity": continuity,
    })
    return {
        "action": "restarted",
        "old_pid": pid,
        "new_pid": new_pid,
        "restart_count": restart_count + 1,
        "continuity": continuity,
    }


def supervise_loop(
    command: list,
    *,
    max_restarts: int = 3,
    check_interval: float = 0.5,
    max_cycles: int | None = None,
) -> dict:
    """Bounded supervision loop. Halts at restart limit or max_cycles."""
    restart_count = 0
    cycle = 0
    last_result: dict = {}

    while True:
        if max_cycles is not None and cycle >= max_cycles:
            break
        result = supervise_once(command, restart_count=restart_count, max_restarts=max_restarts)
        last_result = result
        if result["action"] == "restart_limit_reached":
            break
        if result["action"] == "restarted":
            restart_count = result["restart_count"]
        cycle += 1
        if check_interval > 0:
            time.sleep(check_interval)

    return {"cycles": cycle, "restart_count": restart_count, "last_result": last_result}


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
