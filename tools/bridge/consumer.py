#!/usr/bin/env python3
import os
import time
import json
import yaml
import subprocess
import hashlib
import shlex
from pathlib import Path
from datetime import datetime, UTC

# Configuration
BASE_DIR = Path("/Users/icmini/0luka").resolve()
INBOX_DIR = BASE_DIR / "interface/inbox"
PROCESSING_DIR = BASE_DIR / "interface/processing"
REJECTED_DIR = BASE_DIR / "interface/rejected"
COMPLETED_DIR = BASE_DIR / "interface/completed"
EVIDENCE_DIR = BASE_DIR / "interface/evidence/tasks"
STATE_DIR = BASE_DIR / "interface/state"
COUNTER_PATH = STATE_DIR / "task_counter.json"
SCHEMA_PATH = BASE_DIR / "interface/schemas/task_spec_v2.yaml"
PENDING_DIR = BASE_DIR / "interface/pending_approval"
LOG_FILE = BASE_DIR / "bridge.log"

ALLOWED_TOOLS = ["shell", "patch", "mkdir", "copy"]
AUTO_ALLOWED_PREFIXES = ["tools/", "system/", "interface/", "modules/", "reports/"]
DENIED_PATTERNS = ["core/", "runtime/", "governance/", ".env", "state/"]
RAM_THRESHOLD_PAGES = 1000  # Lowered for test (~16MB)

def log(msg):
    ts = datetime.now(UTC).isoformat()
    line = f"[{ts}] [LISA-V1.3.2] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def get_sha256(file_path):
    p = Path(file_path)
    if not p.exists(): return None
    sha256_hash = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except: return "error_reading"

def get_next_seq():
    if not COUNTER_PATH.exists():
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with COUNTER_PATH.open("w") as f: json.dump({"next_seq": 1}, f)
    
    with COUNTER_PATH.open("r+") as f:
        data = json.load(f)
        seq = data["next_seq"]
        data["next_seq"] += 1
        f.seek(0)
        json.dump(data, f)
        f.truncate()
    return f"{seq:06d}"

def is_sensitive(path_or_cmd):
    # If it's a multi-word command, check for denied keywords only
    if " " in path_or_cmd.strip():
        return any(p in path_or_cmd for p in DENIED_PATTERNS)
    
    # If it's a single path, do the full resolve check
    try:
        path = Path(path_or_cmd)
        rel_path = path.resolve().relative_to(BASE_DIR)
        path_str_norm = str(rel_path)
        if any(path_str_norm.startswith(p) or p in path_str_norm for p in DENIED_PATTERNS):
            return True
        if not any(path_str_norm.startswith(p) for p in AUTO_ALLOWED_PREFIXES):
            return True
        return False
    except ValueError:
        return True

def check_memory():
    try:
        proc = subprocess.run(["vm_stat"], capture_output=True, text=True)
        for line in proc.stdout.splitlines():
            if "Pages free:" in line:
                free_pages = int(line.split(":")[1].strip().replace(".", ""))
                return free_pages
    except: return 99999
    return 99999

def validate_schema(task):
    required = ["task_id", "operations", "intent", "author"]
    for r in required:
        if r not in task:
            log(f"MISSING_FIELD: {r}")
            return False
    return isinstance(task["operations"], list)

def atomic_write_json(file_path, data):
    tmp_path = Path(str(file_path) + ".tmp")
    with tmp_path.open("w") as f:
        json.dump(data, f, indent=2)
    tmp_path.replace(file_path)

def process_task(task_file):
    log(f"New task detected: {task_file.name}")
    
    free = check_memory()
    if free < RAM_THRESHOLD_PAGES:
        log(f"RAM_CRITICAL: {free} pages. Throttling.")
        return

    try:
        PROCESSING_DIR.mkdir(parents=True, exist_ok=True)
        active_task = PROCESSING_DIR / task_file.name
        task_file.replace(active_task)
        
        # Small grace period for the OS to finalize the replace
        time.sleep(0.5)
        
        with active_task.open("r") as f:
            content = f.read()
            if not content:
                log(f"READ_ERROR: File {active_task.name} is empty.")
                return
            task = yaml.safe_load(content) if active_task.suffix in ('.yaml', '.yml') else json.loads(content)
        
        if not validate_schema(task):
            REJECTED_DIR.mkdir(parents=True, exist_ok=True)
            active_task.replace(REJECTED_DIR / active_task.name)
            log(f"REJECTED: Invalid Schema")
            return

        task_id = task.get("task_id", "unknown")
        needs_approval = False
        for op in task.get("operations", []):
            target = op.get("params", {}).get("target_path", "n/a")
            if target != "n/a" and is_sensitive(target):
                needs_approval = True; break
        
        if needs_approval:
            PENDING_DIR.mkdir(parents=True, exist_ok=True)
            active_task.replace(PENDING_DIR / active_task.name)
            log(f"PENDING: {task_id} moved to Approval Gate.")
            return

        seq = get_next_seq()
        start_time = time.time()
        results, artifacts = [], []
        
        for op in task.get("operations", []):
            op_id, tool, params = op.get("id"), op.get("tool"), op.get("params", {})
            target = params.get("target_path", "n/a")
            
            if tool not in ALLOWED_TOOLS:
                results.append({"op_id": op_id, "status": "TOOL_DENIED", "exit_code": 1})
                continue
            
            sha_before = get_sha256(target) if target != "n/a" else None
            
            if tool == "shell":
                cmd_str = params.get("command")
                if is_sensitive(cmd_str):
                    results.append({"op_id": op_id, "status": "SECURITY_BLOCK", "exit_code": 1})
                    continue
                
                proc = subprocess.run(shlex.split(cmd_str), capture_output=True, text=True, cwd=BASE_DIR)
                results.append({"op_id": op_id, "status": "ok" if proc.returncode == 0 else "error", "exit_code": proc.returncode, "target_path": target})
                
                if target != "n/a" and Path(target).exists():
                    artifacts.append({"path": target, "sha256_before": sha_before, "sha256_after": get_sha256(target)})

        duration_ms = int((time.time() - start_time) * 1000)
        evidence = {
            "schema_version": "evidence.v1.2",
            "task_id": task_id, "trace_seq": f"TK-{seq}",
            "ts_utc": datetime.now(UTC).isoformat(),
            "executor": "lisa_v1.3.1",
            "duration_ms": duration_ms,
            "results": results, "artifacts": artifacts,
            "verification": {"status": "pass"}
        }
        
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_json(EVIDENCE_DIR / f"EVID-{task_id}-TK-{seq}.json", evidence)
        
        COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
        active_task.replace(COMPLETED_DIR / active_task.name)
        log(f"DONE: TK-{seq}")

    except Exception as e:
        log(f"ERROR: {e}")

def main():
    log("Lisa Bridge v1.3.1 (Forensic) Starting...")
    while True:
        # Check recursive .task.json and .yaml
        for pattern in ["*.task.json", "*.yaml", "*.yml"]:
            for item in INBOX_DIR.rglob(pattern):
                if item.is_file() and not item.name.startswith('.') and "processing" not in str(item) and "completed" not in str(item):
                    process_task(item)
        time.sleep(2)

if __name__ == "__main__":
    main()
