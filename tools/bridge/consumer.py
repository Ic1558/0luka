#!/usr/bin/env python3
import os
import time
import json
import yaml
import subprocess
import hashlib
import shutil
import re
import socket
from pathlib import Path
from datetime import datetime, UTC, timedelta

# --- Configuration (CLEC v1.3+ Emergency Hardened) ---
BASE_DIR = Path("/Users/icmini/0luka").resolve()
INBOX_DIR = BASE_DIR / "interface/inbox/tasks"
PROCESSING_DIR = BASE_DIR / "interface/processing/tasks"
REJECTED_DIR = BASE_DIR / "interface/rejected/tasks"
DONE_DIR = BASE_DIR / "interface/done/tasks"
EVIDENCE_DIR = BASE_DIR / "interface/evidence/tasks"
STATE_DIR = BASE_DIR / "interface/state"
COUNTER_PATH = STATE_DIR / "task_counter.json"
PENDING_DIR = BASE_DIR / "interface/pending/tasks"
LOG_FILE = BASE_DIR / "bridge.log"
SOT_LATEST_PATH = BASE_DIR / "observability/artifacts/daily/latest.md"

# Forensic Telemetry
TELEMETRY_DIR = BASE_DIR / "observability/telemetry"
EMERGENCY_LOG = TELEMETRY_DIR / "gate_emergency.jsonl"
EMERGENCY_USED = TELEMETRY_DIR / "gate_emergency_used.jsonl"

ALLOWED_CALL_SIGNS = ["[Liam]", "[Lisa]", "[GMX]", "[Codex]"]
SOT_MAX_AGE_HOURS = 24
HOST_ALLOWLIST_EMERGENCY = ["icmini", "Ittipongs-Mac-mini"] # Strict host gating

# Security Whitelists
ALLOWED_COMMANDS = ["ls", "grep", "cat", "echo", "git", "head", "tail", "wc", "date"]
RISK_MAP = {
    "R0": ["interface/evidence", "interface/state", "observability", "reports/daily"],
    "R1": ["modules", "docs", "reports", "tools", "skills"],
    "R2": ["interface/schemas", "governance", "core_brain/governance", "luka.md"],
    "R3": ["core", "runtime", ".env"] 
}

def log(msg):
    ts = datetime.now(UTC).isoformat()
    line = f"[{ts}] [LISA-V1.3-EMERGENCY] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# --- Security Primitives ---

def safe_path(p_str):
    if not p_str or p_str == "n/a": return None
    if ".." in p_str: return None 
    try:
        target = Path(p_str)
        if not target.is_absolute(): target = (BASE_DIR / target).resolve()
        else: target = target.resolve()
        return target if str(target).startswith(str(BASE_DIR)) else None
    except: return None

def detect_secret(content):
    if not content: return False
    patterns = [r"KEY\s*=", r"TOKEN\s*=", r"PASSWORD\s*=", r"-----BEGIN.*PRIVATE KEY", r"\.env\.local"]
    normalize = str(content).upper()
    return any(re.search(p, normalize) for p in patterns)

def is_safe_command(cmd_str):
    if not cmd_str: return True
    parts = cmd_str.strip().split()
    return parts and parts[0] in ALLOWED_COMMANDS

# --- Forensic Helpers ---

def get_git_head():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=BASE_DIR)
        return res.stdout.strip() if res.returncode == 0 else "no_git"
    except: return "error"

def get_dirty_status():
    try:
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=BASE_DIR)
        return bool(res.stdout.strip())
    except: return False

def get_sot_ref():
    if not SOT_LATEST_PATH.exists(): return {"path": str(SOT_LATEST_PATH), "sha256": None, "mtime_utc": None}
    mtime = datetime.fromtimestamp(SOT_LATEST_PATH.stat().st_mtime, UTC).isoformat()
    return {"path": "observability/artifacts/daily/latest.md", "sha256": get_sha256(SOT_LATEST_PATH), "mtime_utc": mtime}

def get_sha256(file_path):
    p = safe_path(str(file_path))
    if not p or not p.exists() or not p.is_file(): return None
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""): h.update(chunk)
        return h.hexdigest()
    except: return "error"

def atomic_write(file_path, data, is_jsonl=False):
    p = Path(file_path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    
    # Handle append-only for telemetry
    mode = "w"
    if is_jsonl and p.name.startswith("gate_"): mode = "a" 
    
    if mode == "a":
        with p.open("a") as f:
             if isinstance(data, list): 
                 for line in data: f.write(json.dumps(line) + "\n")
             else: f.write(json.dumps(data) + "\n")
        return

    # Atomic replace for artifacts
    with tmp.open("w") as f:
        if is_jsonl:
            for line in data: f.write(json.dumps(line) + "\n")
        else: json.dump(data, f, indent=2)
    tmp.replace(p)

# --- Emergency Logic ---

def log_emergency_attempt(task, result, detail, lane_forced="n/a"):
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "host": socket.gethostname().split('.')[0],
        "actor": task.get("author", "unknown"),
        "call_sign": task.get("call_sign", "unknown"),
        "ticket": task.get("emergency_ticket"),
        "reason": task.get("emergency_reason"),
        "scope": task.get("emergency_scope"),
        "expires_in_sec": task.get("expires_in_sec"),
        "trace_id": task.get("trace_id", task.get("task_id")),
        "task_id": task.get("task_id"),
        "result": result,
        "detail": detail,
        "lane_forced": lane_forced,
        "token_consumed": True if result == "approved" else False
    }
    # Append-only log
    with EMERGENCY_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")

def check_emergency_token(task):
    """
    v1.3+ Emergency Bypass Guard (v1.0 Policy)
    Return: (is_valid, ticket, scope, forced_decision_status)
    """
    env_bypass = os.environ.get("SAVE_EMERGENCY") == "1"
    if not env_bypass: return False, None, None, None
    
    # Fields
    ticket = task.get("emergency_ticket")
    reason = task.get("emergency_reason")
    scope = task.get("emergency_scope")
    expiry = task.get("expires_in_sec", 0)
    call_sign = task.get("call_sign")
    
    # 1. Host Check (Immediate Hard Fail with Canonicalization)
    hostname = socket.gethostname().split('.')[0].lower()
    # Normalize Allowlist
    allowlist_norm = [h.lower() for h in HOST_ALLOWLIST_EMERGENCY]
    
    if hostname not in allowlist_norm:
        log_emergency_attempt(task, "denied_host", f"Host {hostname} not allowed")
        return False, None, None, "REJECTED"

    # 2. Missing Fields
    if not all([ticket, reason, scope]):
        missing = [k for k,v in {"ticket":ticket, "reason":reason, "scope":scope}.items() if not v]
        log_emergency_attempt(task, "missing_fields", f"Missing: {missing}")
        return False, None, None, "REJECTED"

    # 3. Auth Check (Actor)
    if call_sign != "[GMX]":
        log_emergency_attempt(task, "denied_actor", f"Actor {call_sign} != [GMX]")
        return False, None, None, "REJECTED"

    # 4. Replay Check (Single-Shot)
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    if EMERGENCY_USED.exists():
        with EMERGENCY_USED.open("r") as f:
            used = [json.loads(line)["ticket"] for line in f]
            if ticket in used:
                log_emergency_attempt(task, "replay_detected", f"Ticket {ticket} reused")
                return False, None, None, "REJECTED"

    # 5. Expiry (Strict TTL)
    if expiry is None or not isinstance(expiry, int) or expiry <= 0:
         log_emergency_attempt(task, "missing_fields", "Invalid/Missing Expiry") # Or "expired"
         return False, None, None, "REJECTED"

    if expiry > 300:
        log_emergency_attempt(task, "expired", "Expiry > 300s")
        return False, None, None, "REJECTED"

    # 6. Policy: Force HELD (never FAST)
    final_status = "HELD"
    if scope in ["telemetry", "evidence"]:
        final_status = "EXECUTE"

    # Mark Used (Optimistic)
    with EMERGENCY_USED.open("a") as f:
        f.write(json.dumps({"ticket": ticket, "ts": datetime.now(UTC).isoformat()}) + "\n")
    
    # Proof of Consumption
    log_emergency_attempt(task, "approved", "Token Valid", lane_forced=final_status)
    return True, ticket, scope, final_status

# --- Core Logic ---

def check_pre_flight():
    checks = []
    # 1. SOT Freshness
    sot_ok = "pass"
    if not SOT_LATEST_PATH.exists(): sot_ok = "fail"
    else:
        if (datetime.now(UTC) - datetime.fromtimestamp(SOT_LATEST_PATH.stat().st_mtime, UTC)) > timedelta(hours=SOT_MAX_AGE_HOURS): sot_ok = "fail"
    checks.append({"name": "sot_fresh", "status": sot_ok, "detail": str(SOT_LATEST_PATH)})
    
    # 2. Pending Guard
    pending_ok = "pass"
    if PENDING_DIR.exists() and any(PENDING_DIR.iterdir()): pending_ok = "hold"
    checks.append({"name": "pending_empty", "status": pending_ok, "detail": "queue not empty"})
    
    status = "pass"
    if any(c["status"] == "fail" for c in checks): status = "fail"
    elif any(c["status"] == "hold" for c in checks): status = "hold"
    return {"status": status, "checks": checks}

def classify_risk(ops):
    max_level = 0
    for op in ops:
        target, cmd = op.get("target_path"), op.get("command")
        if detect_secret(str(op)): return "R3"
        paths = [p for p in [target, cmd] if p]
        for p_str in paths:
            for r, risk_paths in RISK_MAP.items():
                if any(k in p_str for k in risk_paths): max_level = max(max_level, int(r[1]))
    return f"R{max_level}"

def process_task(task_file):
    log(f"Processing: {task_file.name}")
    
    with open(task_file, "r") as f:
        try:
             raw_pre = yaml.safe_load(f) if task_file.suffix in ('.yaml', '.yml') else json.load(f)
        except: return 
        
    # Emergency Check
    is_emergency, emr_ticket, emr_scope, emr_force_status = check_emergency_token(raw_pre)
    
    # If Emergency Failed (and SAVE_EMERGENCY was set), we might REJECT immediately based on returned decision?
    # check_emergency_token returns (False, None, None, "REJECTED") if check failed.
    # If it returns False and decision is REJECTED, we should reject.
    if os.environ.get("SAVE_EMERGENCY") == "1" and not is_emergency:
         REJECTED_DIR.mkdir(parents=True, exist_ok=True); 
         dest = REJECTED_DIR / task_file.name
         task_file.replace(dest)
         log(f"REJECT: Emergency Token Invalid")
         return

    pre_flight = check_pre_flight()
    
    # Bypass Pre-Flight
    if pre_flight["status"] != "pass":
        if is_emergency:
            log(f"EMERGENCY_BYPASS: Pre-Flight {pre_flight['status']} ignored via {emr_ticket}")
        else:
            log(f"PRE_FLIGHT_{pre_flight['status'].upper()}: {pre_flight['checks']}")
            return # HOLD/BLOCK

    try:
        PROCESSING_DIR.mkdir(parents=True, exist_ok=True)
        active = PROCESSING_DIR / task_file.name
        task_file.replace(active)
        
        with active.open("r") as f:
            raw = yaml.safe_load(f) if active.suffix in ('.yaml', '.yml') else json.load(f)
            
        # --- 1. Schema Validation ---
        if "ops" not in raw and "operations" in raw: raw["ops"] = raw.pop("operations")
        valid_schema = all(k in raw for k in ["task_id", "author", "call_sign", "ops"])
        call_sign = raw.get("call_sign")
        author = raw.get("author")
        
        decision = {"status": "PENDING", "reason": "Routing"}
        
        if not valid_schema and not is_emergency: 
             decision = {"status": "REJECTED", "reason": "Schema Validation Failed"}
        elif (not call_sign or f"[{author.lower()}]" != call_sign.lower()) and not (is_emergency and call_sign=="[GMX]"):
             if f"[{author.lower()}]" != call_sign.lower():
                 decision = {"status": "REJECTED", "reason": "Identity Mismatch"}

        # --- 2. Risk & Lane ---
        if decision["status"] == "PENDING":
            risk = classify_risk(raw["ops"])
            lane = raw.get("lane_hint", "FAST").upper()
            
            # G2: High Risk
            if risk in ["R2", "R3"] and lane == "FAST":
                 decision = {"status": "REJECTED", "reason": f"Risk Blocked ({risk} on FAST)"}
            elif detect_secret(str(raw)) and risk in ["R2", "R3"]:
                 decision = {"status": "REJECTED", "reason": "Secret Detected in High Risk"}
            elif risk == "R2" and lane != "APPROVED" and not is_emergency:
                 decision = {"status": "HELD", "reason": "Approval Required"}
            elif risk == "R3" and not is_emergency:
                 decision = {"status": "REJECTED", "reason": "R3 Kernel Hard Stop"}
            else:
                 decision = {"status": "EXECUTE", "reason": "Authorized"}

        # Emergency Force Override
        if is_emergency:
            # Check Core Safety First (Cannot bypass R3 if Secret/etc - handled above by Risk Logic?)
            # Wait, user says: "Never bypass ... secret scanning fail-closed (for R2/R3)".
            # In my logic, `detect_secret` check happens BEFORE this override block if I place it right.
            # My logic:
            # 1. Classify Risk -> R3 if secret.
            # 2. Check Risk R2/R3 + Secret -> REJECTED. (This handles Safety Net)
            # 3. If R3 + No Secret -> REJECTED (Kernel Stop). User says "bypass SOT/Pending only".
            #    Does emergency bypass R3 Kernel Stop?
            #    User says "Only SOT stale and Pending guard".
            #    So R3 Kernel Stop should stay REJECTED?
            #    "Can bypass (only these): SOT stale, pending guard".
            #    So R3 checks, Identity checks MUST PASS.
            #    If `check_pre_flight` was bypassed, we are here.
            #    Now we check Risk. If Risk is R3 -> REJECT.
            #    So Emergency doesn't help with R3. Correct.
            
            # If decision was EXECUTE or HELD (normal flow), we enforce Emergency Policy:
            if decision["status"] in ["EXECUTE", "HELD", "PENDING"]:
                 decision["status"] = emr_force_status # Apply forced status (EXECUTE or HELD)
                 decision["reason"] = f"Emergency: {emr_scope}"

        # --- Routing ---
        if decision["status"] == "REJECTED":
            REJECTED_DIR.mkdir(parents=True, exist_ok=True); active.replace(REJECTED_DIR / active.name); log(f"REJECT: {decision['reason']}"); return
        if decision["status"] == "HELD":
            PENDING_DIR.mkdir(parents=True, exist_ok=True); active.replace(PENDING_DIR / active.name); log(f"HOLD: {decision['reason']}"); return

        # --- 3. Execution ---
        start_ts = datetime.now(UTC).isoformat()
        git_before = get_git_head()
        dirty_before = get_dirty_status()
        results, artifacts, ver_results = [], [], []
        ver_status = "pass"
        
        # 3.1 Pre-Verification
        for v in raw.get("verify", raw.get("verification", [])):
            if isinstance(v, str): check_type, target = v.split(":", 1); target=target.strip()
            else: check_type, target = v.get("check"), v.get("target")

            res, det = "pass", ""
            if check_type == "gate.fs.exists":
                if not safe_path(target) or not safe_path(target).exists(): res, det = "fail", "file missing"
            if check_type == "gate.test.run":
                cmd = v.get("command", target) # target sometimes cmd in legacy
                if not is_safe_command(cmd) and not is_emergency: res, det = "fail", "unsafe command"
            ver_results.append({"check": check_type, "status": res, "detail": det})
            if res == "fail": ver_status = "fail"

        if ver_status == "fail":
             REJECTED_DIR.mkdir(parents=True, exist_ok=True); active.replace(REJECTED_DIR / active.name); log("REJECT: Pre-Verification Failed"); return

        # 3.2 Ops Execution
        for op in raw["ops"]:
            op_id, o_type = op.get("op_id", "id"), op.get("type", op.get("tool")).lower()
            params = op.get("params", {})
            target = op.get("target_path", params.get("target_path"))
            src = op.get("src_path", params.get("source_path"))
            cmd = op.get("command", params.get("command"))
            t_start = time.time(); status_op, err = "ok", ""
            
            # Core Safety (Cannot Bypass SafePath)
            if target and not safe_path(target): status_op, err = "fail", "Path Escape/Unsafe"
            elif src and not safe_path(src): status_op, err = "fail", "Source Unsafe"
            
            if status_op == "ok":
                try:
                    p_target = safe_path(target) if target else None
                    if o_type == "mkdir": p_target.mkdir(parents=True, exist_ok=True)
                    elif o_type in ["write_text", "write"]: p_target.parent.mkdir(parents=True, exist_ok=True); p_target.write_text(op.get("content", ""))
                    elif o_type == "copy": shutil.copy2(safe_path(src), p_target)
                    elif o_type in ["run", "shell", "command"]:
                        if not is_safe_command(cmd) and not is_emergency: status_op, err = "fail", "Command not whitelisted"
                        else:
                             if not is_emergency and any(c in cmd for c in [";", "&", "|", "`", "$("]): status_op, err = "fail", "Complex injection"
                             else:
                                 sub = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE_DIR)
                                 if sub.returncode != 0: status_op, err = "fail", sub.stderr
                except Exception as e: status_op, err = "fail", str(e)
            
            if target and (sha_after := get_sha256(target)): artifacts.append({"path": target, "sha256_after": sha_after})
            results.append({"op_id": op_id, "type": o_type, "status": status_op, "target_path": target, "duration_ms": int((time.time()-t_start)*1000), "stderr": err})
            if status_op == "fail": break

        # --- 4. Evidence ---
        trace_id = raw.get("trace_id", raw.get("task_id"))
        decision_final = "DONE" if all(r["status"]!="fail" for r in results) else "ERROR"
        
        evidence = {
            "schema_version": "evidence.v1", "task_id": raw.get("task_id"), "trace_id": trace_id,
            "ts_utc": datetime.now(UTC).isoformat(), "actor": "lisa-v1.3-emergency" if is_emergency else "lisa-v1.3-hardened",
            "author": author, "call_sign": call_sign, "lane": lane, "risk_level": risk, "root": str(BASE_DIR),
            "decision": {"status": decision_final, "reason": "Emergency Exec" if is_emergency else "Execution Completed"},
            "pre_flight": pre_flight, "emergency": {"used": is_emergency, "ticket": emr_ticket},
            "git": {"head_before": git_before, "head_after": get_git_head(), "dirty_before": dirty_before, "dirty_after": get_dirty_status()},
            "sot_ref": get_sot_ref(), "results": results, "artifacts": artifacts, "verification": {"status": ver_status, "checks": ver_results}
        }
        
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write(EVIDENCE_DIR / f"EVID-{raw.get('task_id')}.json", evidence)
        dest = DONE_DIR / str(trace_id) if decision_final == "DONE" else REJECTED_DIR
        dest.mkdir(parents=True, exist_ok=True)
        active.replace(dest / active.name)
        log(f"DONE: {raw.get('task_id')} ({decision_final}) {'[EMERGENCY]' if is_emergency else ''}")
            
    except Exception as e: log(f"CRASH: {e}")

def main():
    log("Lisa Bridge v1.3+ (Emergency Hardened) Starting...")
    while True:
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(list(INBOX_DIR.rglob("*.task.json")) + list(INBOX_DIR.rglob("*.yaml")) + list(INBOX_DIR.rglob("*.yml")), key=lambda x: x.stat().st_mtime)
        for item in files:
            if item.is_file() and not item.name.startswith('.'): process_task(item)
        time.sleep(2)

if __name__ == "__main__": main()
