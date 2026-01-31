#!/usr/bin/env python3
# tools/bridge/lisa_executor.py
# Reference implementation for Executor Contract v1 (TaskSpec v1)

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def atomic_write(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)

class Logger:
    def __init__(self, lane: Optional[str], worker_id: str, log_file: Path):
        self.lane = lane or "global"
        self.worker_id = worker_id
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
    def _write(self, msg: str, task_id: str = "-", state: str = "IDLE"):
        ts = now_utc_iso()
        line = f"{ts} | {self.lane} | {self.worker_id} | {task_id} | {state} | {msg}\n"
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(line)
        print(line.strip())

    def info(self, msg: str, task_id: str = "-", state: str = "IDLE"):
        self._write(msg, task_id, state)
    
    def error(self, msg: str, task_id: str = "-", state: str = "ERROR"):
        self._write(f"ERROR: {msg}", task_id, state)

def process_task(root: Path, inbox_file: Path, inflight_base: Path, outbox_base: Path, lane: Optional[str], log: Logger) -> bool:
    start_ts = now_utc_iso()
    start_time = time.time()
    
    # 1. Claim -> In-Flight
    inflight_dir = inflight_base / "lisa"
    inflight_dir.mkdir(parents=True, exist_ok=True)
    claimed = inflight_dir / inbox_file.name
    inbox_file.replace(claimed)
    
    # 2. Parse task
    try:
        task = json.loads(claimed.read_text(encoding="utf-8"))
        task_id = str(task.get("task_id", "unknown"))
        payload = task.get("payload", {})
        intent = task.get("intent", "noop")
    except Exception as e:
        if claimed.exists(): claimed.unlink()
        log.error(f"failed to parse task: {e}")
        return False
    
    pending_base = root / "interface/pending"
    if lane: pending_base = pending_base / lane
    pending_dir = pending_base / "tasks" / task_id
    
    try:
        log.info("started execution", task_id, "RUNNING")
        # A1/A2: State Transition -> RUNNING
        if pending_dir.exists():
            status_path = pending_dir / "status.json"
            if status_path.exists():
                try:
                    status = json.loads(status_path.read_text())
                    status["status"] = "RUNNING"
                    status["ts_utc"] = now_utc_iso()
                    status["worker_id"] = "lisa-0"
                    atomic_write(status_path, status)
                except: pass
            
            # Lease & Heartbeat (A3)
            lease_path = pending_dir / "lease.json"
            if lease_path.exists():
                atomic_write(lease_path, {
                    "owner": {"worker_id": "lisa-0", "pid": os.getpid(), "host": "local"},
                    "issued_at": now_utc_iso(),
                    "expires_at": (datetime.now(timezone.utc).timestamp() + 60) # 60s TTL
                })
            
            atomic_write(pending_dir / "heartbeat.json", {
                "ts_utc": now_utc_iso(),
                "status": "RUNNING",
                "progress": 0.1
            })

            tl_running = {"ts_utc": now_utc_iso(), "event": "RUNNING", "task_id": task_id, "worker_id": "lisa-0"}
            with (pending_dir / "timeline.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(tl_running, ensure_ascii=False) + "\n")

        # 3. Execute
        cmd = ["echo", f"Executing LISA task: {intent} for {task_id}"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        stdout = res.stdout
        stderr = res.stderr
        exit_code = res.returncode
        
        # 4. Prepare Result
        result_payload = {
            "task_id": task_id,
            "executor": "lisa",
            "ok": exit_code == 0,
            "status": "COMPLETED" if exit_code == 0 else "FAILED",
            "ts_utc": now_utc_iso(),
            "duration_sec": round(time.time() - start_time, 2),
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "result": {"summary": f"LISA {intent} finished", "details": payload}
        }
        
        # 5. Outbox
        outbox_dir = outbox_base / "lisa"
        outbox_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(outbox_dir / f"{task_id}.result.json", result_payload)
        
        log.info("completed successfully", task_id, "DONE")
        return True
    except Exception as e:
        log.error(f"execution failed: {e}", task_id, "FAILED")
        error_result = {
            "task_id": task_id,
            "executor": "lisa",
            "ok": False,
            "status": "FAILED",
            "ts_utc": now_utc_iso(),
            "stderr": f"LISA_EXECUTOR_CRASH: {e}",
            "result": {"error": str(e)}
        }
        outbox_dir = outbox_base / "lisa"
        outbox_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(outbox_dir / f"{task_id}.result.json", error_result)
        if claimed.exists(): claimed.unlink()
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("root_pos", nargs="?", default=None)
    parser.add_argument("--root", default=None)
    parser.add_argument("--lane", default=None)
    parser.add_argument("--worker-id", default="lisa-0")
    args = parser.parse_args()
    
    root_str = args.root or args.root_pos or os.environ.get("ROOT") or os.environ.get("LUKA_ROOT") or os.path.expanduser("~/0luka")
    root = Path(root_str).resolve()
    
    inbox = root / "interface/inbox/tasks/lisa"
    inflight = root / "interface/inflight/tasks"
    outbox = root / "interface/outbox/tasks"
    telemetry = root / "observability/telemetry/executor_lisa.latest.json"
    log_file = root / f"logs/workers/{args.worker_id}.log"
    log = Logger(args.lane, args.worker_id, log_file)

    # Symlink for summary tool visibility
    comp_log_dir = root / "logs/components/lisa_executor"
    comp_log_dir.mkdir(parents=True, exist_ok=True)
    comp_current = comp_log_dir / "current.log"
    if comp_current.is_symlink() or comp_current.exists(): comp_current.unlink()
    try: comp_current.symlink_to(log_file)
    except: pass

    if not inbox.exists():
        # No work today
        atomic_write(telemetry, {"ts": now_utc_iso(), "status": "idle", "processed": 0})
        return

    tasks = sorted(inbox.glob("*.task.json"))
    processed = 0
    for t in tasks:
        if process_task(root, t, inflight, outbox, args.lane, log):
            processed += 1
            
    atomic_write(telemetry, {
        "ts": now_utc_iso(),
        "status": "ok",
        "processed": processed,
        "last_run": now_utc_iso()
    })
    print(f"[{now_utc_iso()}] lisa_executor finished | processed={processed}")

if __name__ == "__main__":
    main()
