"""AG-P6: Sovereign Runtime Service — production heartbeat daemon.

Designed for launchd KeepAlive management. Runs a tick loop:
  - write heartbeat record
  - run supervisor health check
  - sleep TICK_INTERVAL seconds
  - repeat until SIGTERM/SIGINT

Evidence written to LUKA_RUNTIME_ROOT/state/:
  runtime_sovereign_service_latest.json   — last tick
  runtime_sovereign_service_log.jsonl     — all ticks
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

TICK_INTERVAL = 15  # seconds between heartbeat ticks
SERVICE_VERSION = "1.0.0"
_running = True


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _log_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT") or str(Path.home() / "0luka_runtime")
    d = Path(rt) / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_supervisor_check() -> dict:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from runtime.headless_supervisor import run_supervisor_check
        return run_supervisor_check(operator_id="sovereign_service")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _tick(run_id: str, tick: int) -> dict:
    sd = _state_dir()
    ts = _now()
    supervisor = _run_supervisor_check()
    record = {
        "run_id": run_id,
        "tick": tick,
        "pid": os.getpid(),
        "service_version": SERVICE_VERSION,
        "supervisor_status": supervisor.get("overall_status") or supervisor.get("error"),
        "ts": ts,
        "governed": True,
    }
    _atomic_write(sd / "runtime_sovereign_service_latest.json", record)
    _append_jsonl(sd / "runtime_sovereign_service_log.jsonl", record)
    return record


def _handle_signal(signum, frame):
    global _running
    sd = _state_dir()
    _append_jsonl(sd / "runtime_sovereign_service_log.jsonl", {
        "event": "shutdown",
        "signal": signum,
        "pid": os.getpid(),
        "ts": _now(),
    })
    _running = False


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    run_id = str(uuid.uuid4())
    tick = 0

    # Log startup
    _append_jsonl(_state_dir() / "runtime_sovereign_service_log.jsonl", {
        "event": "startup",
        "run_id": run_id,
        "pid": os.getpid(),
        "service_version": SERVICE_VERSION,
        "ts": _now(),
    })

    while _running:
        try:
            _tick(run_id, tick)
        except Exception as exc:
            # Never crash — write error record and continue
            _append_jsonl(_state_dir() / "runtime_sovereign_service_log.jsonl", {
                "event": "tick_error",
                "tick": tick,
                "error": str(exc)[:300],
                "ts": _now(),
            })
        tick += 1
        # Sleep in small increments to check _running flag
        for _ in range(TICK_INTERVAL * 2):
            if not _running:
                break
            time.sleep(0.5)


if __name__ == "__main__":
    main()
