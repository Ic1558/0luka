from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:
    print("[FATAL] PyYAML is required. Install: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

ISOZ = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def repo_rel_guard(p: str) -> None:
    if not isinstance(p, str) or not p.strip():
        raise ValueError("path empty")
    if p.startswith("/") or p.startswith("~") or ":\\" in p or p.startswith("\\\\"):
        raise ValueError(f"absolute/tilde path forbidden: {p}")
    parts = Path(p).parts
    if ".." in parts:
        raise ValueError(f"path traversal forbidden: {p}")

def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise ValueError("task must be JSON object")
    return data

def atomic_write(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)

def load_schema(path: Path) -> dict[str, Any]:
    s = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    if not isinstance(s, dict):
        raise ValueError("schema must be mapping")
    return s

def validate(task: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errs: list[str] = []

    required = schema.get("required") or []
    if isinstance(required, list):
        for k in required:
            if k not in task:
                errs.append(f"missing:{k}")

    # Time validation (support ts_utc or created_at_utc)
    ts = str(task.get("ts_utc") or task.get("created_at_utc") or "").strip()
    if not ts or not ISOZ.match(ts):
        errs.append(f"invalid:timestamp_format:{ts}")

    lane = task.get("lane")
    if lane not in (schema.get("rules", {}).get("lane", {}).get("allowed") or []):
        errs.append("invalid:lane")

    exec_allowed = schema.get("executor", {}).get("allowed") or schema.get("rules", {}).get("executor", {}).get("allowed") or []
    if task.get("executor") not in exec_allowed:
        errs.append("invalid:executor")

    # Optional policies
    ep_allowed = schema.get("rules", {}).get("evidence_policy", {}).get("allowed") or []
    rp_allowed = schema.get("rules", {}).get("reply_policy", {}).get("allowed") or []
    if task.get("evidence_policy") and task.get("evidence_policy") not in ep_allowed:
        errs.append("invalid:evidence_policy")
    if task.get("reply_policy") and task.get("reply_policy") not in rp_allowed:
        errs.append("invalid:reply_policy")

    # Path hygiene inside payload if present
    payload = task.get("payload") or {}
    if not isinstance(payload, dict):
        errs.append("invalid:payload")
        return errs

    # standard move intent example (optional)
    if task.get("intent") == "librarian_move":
        moves = payload.get("moves") or []
        if not isinstance(moves, list) or not moves:
            errs.append("invalid:payload.moves")
        else:
            for m in moves:
                if not isinstance(m, dict):
                    errs.append("invalid:move")
                    continue
                try:
                    repo_rel_guard(str(m.get("src", "")).strip())
                    repo_rel_guard(str(m.get("dst", "")).strip())
                except Exception as e:
                    errs.append(f"invalid:path:{e}")

    return errs

@dataclass
class Paths:
    root: Path
    inbox: Path
    processing: Path
    rejected: Path
    inflight: Path
    outbox: Path
    evidence_base: Path
    done_base: Path
    pending_base: Path
    telemetry_latest: Path
    schema: Path
    schema_v2: Path
    lock_dir: Path
    lane: str | None
    worker_id: str
    log_file: Path
    save_now: Path | None

class Logger:
    def __init__(self, lane: str | None, worker_id: str, log_file: Path):
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

def acquire_lock(lock_dir: Path, ttl_sec: int = 600) -> bool:
    import platform
    import time
    
    owner_file = lock_dir / "owner.json"
    
    try:
        lock_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        # Existing lock, check age
        if owner_file.exists():
            try:
                owner = json.loads(owner_file.read_text())
                started_at = owner.get("started_at", 0)
                if time.time() - started_at < ttl_sec:
                    return False # Valid lock exists
            except:
                pass
        # Stale or corrupt lock
        stale_id = int(time.time())
        try:
            lock_dir.rename(lock_dir.parent / f".lock_stale_{stale_id}")
        except:
            shutil.rmtree(lock_dir, ignore_errors=True)
            
        # Try again after clearing
        try: lock_dir.mkdir(parents=True, exist_ok=False)
        except: return False

    # Write new owner
    owner = {
        "pid": os.getpid(),
        "host": platform.node(),
        "started_at": time.time(),
        "ts_utc": now_utc_iso()
    }
    atomic_write(owner_file, owner)
    return True

def release_lock(lock_dir: Path) -> None:
    shutil.rmtree(lock_dir, ignore_errors=True)

def p(root: Path, lane: str | None = None, worker_id: str = "bridge-0") -> Paths:
    tools_save = root / "tools/save_now.zsh"
    root_save = root / "save_now.zsh"
    save_now = tools_save if tools_save.exists() else (root_save if root_save.exists() else None)

    l_inbox = root / "artifacts/tasks/open"
    # Note: open tasks might not be in lanes yet, but we allow it
    if lane: l_inbox = l_inbox / lane

    l_pending = root / "artifacts/tasks/pending"
    if lane: l_pending = l_pending / lane
    l_pending = l_pending / "tasks"

    l_evidence = root / "artifacts/tasks/evidence"
    if lane: l_evidence = l_evidence / lane
    l_evidence = l_evidence / "tasks"

    l_inflight = root / "interface/processing/tasks"
    if lane: l_inflight = l_inflight / lane

    l_outbox = root / "interface/outbox/tasks"
    # outbox usually divided by executor, not lane

    l_done = root / "artifacts/tasks/done"
    if lane: l_done = l_done / lane
    l_done = l_done / "tasks"

    return Paths(
        root=root,
        inbox=l_inbox,
        processing=l_inflight,
        outbox=l_outbox,
        inflight=root / "interface/inflight/tasks",
        rejected=root / "interface/rejected/tasks",
        evidence_base=l_evidence,
        done_base=l_done,
        pending_base=l_pending,
        telemetry_latest=root / "observability/telemetry/bridge_consumer.latest.json",
        schema=root / "core/schema/task_spec_v1.yaml",
        schema_v2=root / "core/schema/task_spec_v2.yaml",
        lock_dir=l_inflight / ".lock",
        lane=lane,
        worker_id=worker_id,
        log_file=root / f"logs/workers/{worker_id}.log",
        save_now=save_now,
    )


def ensure_dirs(px: Paths) -> None:
    px.processing.mkdir(parents=True, exist_ok=True)
    px.rejected.mkdir(parents=True, exist_ok=True)
    px.evidence_base.mkdir(parents=True, exist_ok=True)
    px.done_base.mkdir(parents=True, exist_ok=True)
    px.inbox.mkdir(parents=True, exist_ok=True)
    px.outbox.mkdir(parents=True, exist_ok=True)
    px.inflight.mkdir(parents=True, exist_ok=True)
    px.pending_base.mkdir(parents=True, exist_ok=True)

def write_evidence(px: Paths, task_id: str, meta: dict[str, Any], timeline_line: dict[str, Any]) -> Path:
    ev = px.evidence_base / task_id
    ev.mkdir(parents=True, exist_ok=True)
    atomic_write(ev / "meta.json", meta)
    with (ev / "timeline.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(timeline_line, ensure_ascii=False) + "\n")
    return ev

def call_save_now(px: Paths, phase: str, task_id: str, title: str) -> None:
    if not px.save_now:
        return
    # conservative: if save_now exists, call it; otherwise skip silently
    os.system(f'"{px.save_now}" --phase {phase} --trace-id {task_id} --agent-id bridge --title "{title}" --in "" >/dev/null 2>&1 || true')

def process_outbox(px: Paths, ts: str) -> tuple[int, int]:
    """
    Module #4: Consume executor results from interface/outbox/tasks/<executor>/
    Expected file: <task_id>.result.json
    """
    import json
    processed = 0
    failed = 0

    for exec_dir in sorted(px.outbox.glob("*")):
        if not exec_dir.is_dir():
            continue
        for rf in sorted(exec_dir.glob("*.result.json")):
            try:
                data = json.loads(rf.read_text(encoding="utf-8", errors="replace"))
                task_id = str(data.get("task_id", "")).strip()
                executor = str(data.get("executor", exec_dir.name)).strip() or exec_dir.name
                ok = bool(data.get("ok", False))
                status = str(data.get("status", "COMPLETED" if ok else "FAILED"))
                result_obj = data.get("result", {})

                if not task_id:
                    raise ValueError("missing task_id")

                ev = px.evidence_base / task_id
                ev.mkdir(parents=True, exist_ok=True)

                # evidence artifacts
                (ev / "result.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

                tl = {"ts_utc": ts, "event": "RESULT_RECEIVED", "task_id": task_id, "executor": executor, "status": status, "ok": ok}
                with (ev / "timeline.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(tl, ensure_ascii=False) + "\n")

                # Module #9: Update Pending State
                pending_dir = px.pending_base / task_id
                if pending_dir.exists():
                    with (pending_dir / "timeline.jsonl").open("a", encoding="utf-8") as f:
                        f.write(json.dumps(tl, ensure_ascii=False) + "\n")
                    
                    if ok:
                        atomic_write(pending_dir / "status.json", {
                            "ts_utc": ts, "status": "DONE", "task_id": task_id, "executor": executor
                        })
                        tl_done = {"ts_utc": ts, "event": "DONE", "task_id": task_id}
                        with (pending_dir / "timeline.jsonl").open("a", encoding="utf-8") as f:
                            f.write(json.dumps(tl_done, ensure_ascii=False) + "\n")
                    else:
                        # Handle Retry/Dead-letter (A4)
                        att_path = pending_dir / "attempt.json"
                        att = {"attempt": 1, "max_attempts": 3, "last_error_code": None, "last_error_at": None, "next_eligible_at": ts}
                        if att_path.exists():
                            try: att = json.loads(att_path.read_text())
                            except: pass
                        
                        att["attempt"] += 1
                        att["last_error_at"] = ts
                        
                        if att["attempt"] <= att["max_attempts"]:
                            # Schedule Retry
                            backoff = 30 * (att["attempt"] - 1) # simple: 30, 60, ...
                            import time
                            next_ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() + backoff
                            next_utc = datetime.fromtimestamp(next_ts, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                            att["next_eligible_at"] = next_utc
                            
                            atomic_write(pending_dir / "status.json", {
                                "ts_utc": ts, "status": "FAILED", "task_id": task_id, "executor": executor, "note": f"Retry {att['attempt']}/{att['max_attempts']} at {next_utc}"
                            })
                            tl_retry = {"ts_utc": ts, "event": "RETRY_SCHEDULED", "task_id": task_id, "attempt": att["attempt"], "next_eligible_at": next_utc}
                            with (pending_dir / "timeline.jsonl").open("a", encoding="utf-8") as f:
                                f.write(json.dumps(tl_retry, ensure_ascii=False) + "\n")
                        else:
                            # DEAD LETTER
                            atomic_write(pending_dir / "status.json", {
                                "ts_utc": ts, "status": "DEAD_LETTER", "task_id": task_id, "executor": executor, "note": "Max attempts reached."
                            })
                            tl_dl = {"ts_utc": ts, "event": "DEAD_LETTER", "task_id": task_id, "reason": "max_attempts"}
                            with (pending_dir / "timeline.jsonl").open("a", encoding="utf-8") as f:
                                f.write(json.dumps(tl_dl, ensure_ascii=False) + "\n")
                                
                        atomic_write(att_path, att)

                final = {
                    "ts_utc": ts,
                    "task_id": task_id,
                    "ok": ok,
                    "status": status,
                    "executor": executor,
                    "result": result_obj,
                    "note": "Module #4: outbox result consumed and finalized.",
                }
                atomic_write(px.done_base / f"{task_id}.done.final.json", final)

                # Move into inflight archive
                infl = px.inflight / executor
                infl.mkdir(parents=True, exist_ok=True)
                try:
                    rf.replace(infl / rf.name)
                except Exception:
                    pass

                call_save_now(px, "done", task_id, f"final:{task_id}")
                call_save_now(px, "reply", task_id, f"final:{task_id}")

                processed += 1
            except Exception:
                failed += 1

    return processed, failed

def process_one(px: Paths, task_path: Path, schema: dict[str, Any], log: Logger) -> int:
    ts = now_utc_iso()

    # claim -> processing
    claimed = px.processing / task_path.name
    task_path.replace(claimed)

    try:
        # parse
        if claimed.suffix == ".md":
            # Transform MD to a TaskSpec v2 object
            content = claimed.read_text(encoding="utf-8")
            task = {
                "version": 2,
                "task_id": claimed.name,
                "created_at_utc": ts,
                "actor": "human",
                "lane": px.lane or "task",
                "intent": "process_doc",
                "executor": "lisa",
                "inputs": {"content": content, "source": str(claimed)},
                "outputs_expected": {},
                "reply_to": "interface/outbox/tasks"
            }
        else:
            task = json.loads(claimed.read_text(encoding="utf-8", errors="replace"))

        task_id = str(task.get("task_id", "unknown"))
        log.info(f"processing task v{task.get('version',1)}", task_id, "START")
        
        # Decide schema (v1 or v2)
        active_schema = schema
        if "created_at_utc" in task or task.get("version") == 2:
            try:
                active_schema = load_schema(px.schema_v2) 
            except: pass
            
        errs = validate(task, active_schema)
        if errs:
            reason = {"ts_utc": ts, "ok": False, "errors": errs}
            atomic_write(px.rejected / (claimed.name + ".reason.json"), reason)
            claimed.replace(px.rejected / claimed.name)
            return 0

        task_id = str(task["task_id"])
        intent = str(task["intent"])
        executor = str(task.get("executor") or "shell") # Default for v1
        title = f"{intent} -> {executor}"

        # Module #7 & #9: Create Pending State (Worker Contract v2)
        pending_dir = px.pending_base / task_id
        pending_dir.mkdir(parents=True, exist_ok=True)
        
        meta = {
            "ts_utc": ts,
            "task_id": task_id,
            "intent": intent,
            "executor": executor,
            "lane": task.get("lane") or "task",
            "actor": task.get("actor") or "unknown",
            "version": task.get("version") or 1,
            "evidence_policy": task.get("evidence_policy", active_schema.get("defaults", {}).get("evidence_policy", "minimal")),
            "reply_policy": task.get("reply_policy", active_schema.get("defaults", {}).get("reply_policy", "summary")),
            "outputs_expected": task.get("outputs_expected", {}),
            "reply_to": task.get("reply_to", "interface/outbox/tasks"),
            "parent_task_id": task.get("parent_task_id"),
            "handoff": task.get("handoff"),
        }
        
        # A1: Worker Contract v2 initialization
        atomic_write(pending_dir / "meta.json", meta)
        atomic_write(pending_dir / "payload.json", task)
        atomic_write(pending_dir / "status.json", {
            "ts_utc": ts, 
            "status": "PENDING", 
            "task_id": task_id, 
            "worker_id": None,
            "attempt": 1,
            "lease_expires_at": None
        })
        atomic_write(pending_dir / "attempt.json", {
            "attempt": 1,
            "max_attempts": task.get("max_attempts", 3),
            "last_error_code": None,
            "last_error_at": None,
            "next_eligible_at": ts
        })
        atomic_write(pending_dir / "lease.json", {
            "owner": None,
            "issued_at": None,
            "expires_at": None
        })
        
        # Initialize empty result/error if needed, or leave for worker
        
        # Original Evidence flow
        tl = {"ts_utc": ts, "event": "START", "task_id": task_id, "intent": intent}
        write_evidence(px, task_id, meta, tl)
        
        # Append to pending timeline too (Module #7 audit)
        tl_p = {"ts_utc": ts, "event": "PENDING", "task_id": task_id, "intent": intent}
        with (pending_dir / "timeline.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(tl, ensure_ascii=False) + "\n") # START
            f.write(json.dumps(tl_p, ensure_ascii=False) + "\n") # PENDING
            if task.get("handoff"):
                h = task["handoff"]
                tl_h = {"ts_utc": ts, "event": "HANDOFF", "task_id": task_id, "from": h.get("from_lane"), "to": h.get("to_lane")}
                f.write(json.dumps(tl_h, ensure_ascii=False) + "\n")

        call_save_now(px, "plan", task_id, title)

        # Dispatch (Module #3):
        # We always dispatch to the global executor inbox root
        global_inbox_root = px.root / "interface/inbox/tasks"
        exec_inbox = global_inbox_root / executor
        exec_inbox.mkdir(parents=True, exist_ok=True)

        tl2 = {"ts_utc": ts, "event": "DISPATCHED", "task_id": task_id, "executor": executor}
        ev = px.evidence_base / task_id
        with (ev / "timeline.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(tl2, ensure_ascii=False) + "\n")
        with (pending_dir / "timeline.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(tl2, ensure_ascii=False) + "\n")

        # Update Status to DISPATCHED
        atomic_write(pending_dir / "status.json", {
            "ts_utc": ts, 
            "status": "DISPATCHED", 
            "task_id": task_id, 
            "executor": executor,
            "worker_id": None,
            "attempt": 1,
            "lease_expires_at": None
        })

        dispatched = exec_inbox / f"{task_id}.task.json"
        claimed.replace(dispatched)

        # Done marker for the bridge consumer's "dispatch" phase
        result = {
            "ts_utc": ts,
            "task_id": task_id,
            "ok": True,
            "status": "DISPATCHED",
            "executor": executor,
            "note": "Module #9: Inbox -> Pending -> Dispatched (Worker Contract v2).",
        }
        atomic_write(px.done_base / f"{task_id}.done.json", result)

        call_save_now(px, "done", task_id, title)
        call_save_now(px, "reply", task_id, title)
        log.info(f"dispatched to {executor}", task_id, "DISPATCHED")
        return 1

    except Exception as e:
        log.error(f"critical failure: {e}", state="CRASH")
        reason = {"ts_utc": ts, "ok": False, "errors": [f"{type(e).__name__}: {e}"]}
        atomic_write(px.rejected / (claimed.name + ".reason.json"), reason)
        try:
            claimed.replace(px.rejected / claimed.name)
        except Exception:
            pass
        return 0

def process_retries(px: Paths, ts: str) -> int:
    """
    Module #9: Find FAILED tasks in pending/ and re-dispatch if now >= next_eligible_at.
    """
    retried = 0
    if not px.pending_base.exists():
        return 0
    
    now_ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()

    for task_dir in sorted(px.pending_base.glob("*")):
        if not task_dir.is_dir():
            continue
            
        status_path = task_dir / "status.json"
        att_path = task_dir / "attempt.json"
        payload_path = task_dir / "payload.json"
        meta_path = task_dir / "meta.json"
        
        if not status_path.exists() or not att_path.exists() or not payload_path.exists() or not meta_path.exists():
            continue
            
        try:
            status = json.loads(status_path.read_text())
            att = json.loads(att_path.read_text())
            
            if status.get("status") == "FAILED":
                next_ts = datetime.fromisoformat(att["next_eligible_at"].replace("Z", "+00:00")).timestamp()
                if now_ts >= next_ts:
                    # Re-dispatch
                    meta = json.loads(meta_path.read_text())
                    payload = json.loads(payload_path.read_text())
                    executor = meta.get("executor", "shell")
                    task_id = meta["task_id"]
                    
                    exec_inbox = px.inbox / executor
                    exec_inbox.mkdir(parents=True, exist_ok=True)
                    
                    # Update status
                    status["status"] = "DISPATCHED"
                    status["ts_utc"] = ts
                    atomic_write(status_path, status)
                    
                    # Timeline
                    tl = {"ts_utc": ts, "event": "DISPATCHED", "task_id": task_id, "executor": executor, "note": f"Retry {att['attempt']}"}
                    with (task_dir / "timeline.jsonl").open("a", encoding="utf-8") as f:
                        f.write(json.dumps(tl, ensure_ascii=False) + "\n")
                    
                    ev = px.evidence_base / task_id
                    if ev.exists():
                        with (ev / "timeline.jsonl").open("a", encoding="utf-8") as f:
                            f.write(json.dumps(tl, ensure_ascii=False) + "\n")
                            
                    # Dispatch payload
                    atomic_write(exec_inbox / f"{task_id}.task.json", payload)
                    retried += 1
                    
        except Exception as e:
            print(f"[{ts}] error processing retry for {task_dir.name}: {e}")
            
    return retried

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("root", help="Project root path")
    parser.add_argument("--lane", default=None, help="Process only this lane")
    parser.add_argument("--worker-id", default="bridge-0", help="Identity of this process")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    px = p(root, lane=args.lane, worker_id=args.worker_id)
    ensure_dirs(px)
    
    log = Logger(px.lane, px.worker_id, px.log_file)
    # Symlink for summary tool visibility
    comp_log_dir = root / "logs/components/bridge_consumer"
    comp_log_dir.mkdir(parents=True, exist_ok=True)
    comp_current = comp_log_dir / "current.log"
    if comp_current.is_symlink() or comp_current.exists(): comp_current.unlink()
    try: comp_current.symlink_to(px.log_file)
    except: pass

    schema = load_schema(px.schema)
    # Pick up .json and .md (Brain tasks)
    inbox_files = []
    for f in sorted(px.inbox.glob("*")):
        if not f.is_file(): continue
        if f.name.endswith(".task.json") or f.name.endswith(".result.json"): continue
        if f.suffix in [".json", ".md"]:
            inbox_files.append(f)

    if not inbox_files:
        # Check outbox and retries even if no new inbox tasks
        outbox_p, _ = process_outbox(px, now_utc_iso())
        retries_p = process_retries(px, now_utc_iso())
        if outbox_p == 0 and retries_p == 0:
            return 0

    if not acquire_lock(px.lock_dir):
        print(f"[{now_utc_iso()}] bridge_consumer: lock exists and not stale. skipping.")
        return 0

    try:
        ts = now_utc_iso()
        processed = 0
        for f in inbox_files:
            processed += process_one(px, f, schema, log)

        outbox_processed, outbox_failed = process_outbox(px, ts)
        processed += outbox_processed
        
        retried = process_retries(px, ts)
        processed += retried
        
        # Telemetry latest (machine-readable)
        try:
            latest = {
                "ts": ts,
                "module": "bridge_consumer",
                "status": "ok",
                "note": "ran",
                "lane": px.lane,
                "worker_id": px.worker_id,
                "inbox": len(inbox_files),
                "processed": processed,
                "outbox_processed": outbox_processed,
                "outbox_failed": outbox_failed,
                "retried": retried,
                "last_file": inbox_files[-1].name if inbox_files else "",
            }
            atomic_write(px.telemetry_latest, latest)
        except Exception:
            pass

        log.info(f"finished | inbox={len(inbox_files)} processed={processed} outbox={outbox_processed} retried={retried}")
    finally:
        release_lock(px.lock_dir)
        
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
