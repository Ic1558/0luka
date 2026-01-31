#!/usr/bin/env python3
# tools/monitoring/postproc.py
# Phase E: Generic Monitoring Post-Processor v1 (Strict Spec)
# Appends "Agent Monitoring" table to forensic summaries.

import argparse
import fcntl
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# --- Configuration ---
MARKER_BEGIN = "<!-- begin:agent_monitoring -->"
MARKER_END = "<!-- end:agent_monitoring -->"
MARKER_REGEX = re.compile(
    r"<!-- begin:agent_monitoring -->.*?<!-- end:agent_monitoring -->",
    re.MULTILINE | re.DOTALL
)

# Resolve ROOT (Repo-relative)
HERE = Path(__file__).resolve().parent
ROOT_ENV = os.environ.get("ROOT")
ROOT = Path(ROOT_ENV).resolve() if ROOT_ENV else HERE.parent.parent

# Canonical Paths
TARGETS_FILE = ROOT / "system/tools/telemetry/staleness_guard_targets.json"
OUTPUT_FILE = ROOT / "reports/summary/latest.md"
SIDECAR_FILE = ROOT / "reports/summary/latest.monitoring.json"
LOCK_DIR = ROOT / "observability/locks/monitoring_postproc.lock"

# Sentinel checks
SENTINELS = ["luka.md", "IDENTITY.md", ".git"]

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def fail(code: int, msg: str):
    print(f"FATAL: {msg}")
    sys.exit(code)

# --- Spec Compliance V2 ---

def validate_root(root: Path) -> bool:
    # Strict Sentinel Check: Must match ALL 3
    found = 0
    for s in SENTINELS:
        if (root / s).exists(): found += 1
    return found == 3

# --- Locking ---
def acquire_lock():
    LOCK_DIR.parent.mkdir(parents=True, exist_ok=True)
    try:
        LOCK_DIR.mkdir()
    except FileExistsError:
        # Check staleness
        try:
            stat = LOCK_DIR.stat()
            age_s = time.time() - stat.st_mtime
            if age_s > 600: # 10 mins
                print(f"WARN: Stale lock found ({age_s:.0f}s), replacing.")
                timestamp = int(time.time())
                archive = LOCK_DIR.with_name(f"monitoring_postproc.lock.stale.{timestamp}")
                LOCK_DIR.rename(archive)
                LOCK_DIR.mkdir() # retry
            else:
                fail(1, f"Locked by another process (age {age_s:.0f}s)")
        except FileNotFoundError:
             LOCK_DIR.mkdir() # Race condition retry

def release_lock():
    try:
        shutil.rmtree(LOCK_DIR)
    except: pass

# --- IO Utils ---
def atomic_write(path: Path, content: str) -> None:
    # Ensure tmp is in same directory for molecular move
    tmp = path.with_suffix(".tmp_mon")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.chmod(0o644) # Standardize permission
        os.replace(tmp, path) # Atomic replace
    except Exception as e:
        if tmp.exists(): tmp.unlink() # Cleanup
        raise e

def is_safe_path(root: Path, path: Path) -> bool:
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
        # Must be strictly under root (not just parent/child mixup)
        return resolved_root in resolved_path.parents
    except: return False

def get_telemetry(root: Path, rel_path: str) -> Dict[str, Any]:
    # Prevent traversal
    if ".." in rel_path or rel_path.startswith("/"):
        return {"status": "unsafe_path"}

    path = root / rel_path
    if not is_safe_path(root, path):
         return {"status": "unsafe_path"}
    
    if not path.exists(): return {"status": "missing"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except: return {"status": "corrupt"}

# --- Logic ---
def main():
    if not validate_root(ROOT):
        fail(2, f"Invalid ROOT {ROOT} (Missing Sentinels)")

    acquire_lock()
    try:
        _run()
    finally:
        release_lock()

def _run():
    if not TARGETS_FILE.exists():
        fail(2, f"Missing config {TARGETS_FILE}")
    
    try:
        targets_data = json.loads(TARGETS_FILE.read_text(encoding="utf-8"))
        targets = targets_data.get("targets", [])
    except Exception as e:
        fail(2, f"Config parse error {e}")

    # Process Targets
    now = datetime.now(timezone.utc)
    monitoring_rows = []
    sidecar_entries = []
    
    table_head = [
        "module | status | last_ts_utc | age | threshold | critical",
        "---|---|---|---:|---|---"
    ]

    for t in targets:
        module = t.get("module", "unknown")
        rel_path = t.get("path", "")
        threshold_min = t.get("threshold", 0)
        critical = t.get("critical", False)
        
        data = get_telemetry(ROOT, rel_path)
        status = data.get("status", "unknown")
        
        # Timestamp parsing
        ts_str = data.get("ts") or data.get("ts_utc") or data.get("last_run") or ""
        age_str = "-"
        age_val_s = -1
        
        is_stale = False
        is_dead = False
        
        if status in ["missing", "corrupt", "unsafe_path"]:
             icon = "⚫️"
        elif not ts_str:
             status = "no_ts"
             icon = "⚫️"
        else:
            try:
                # Handle Z or +00:00
                if ts_str.endswith("Z"):
                    ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                else:
                    ts_dt = datetime.fromisoformat(ts_str)
                
                delta = now - ts_dt
                age_val_s = delta.total_seconds()
                
                # Format Age
                if age_val_s < 60: age_str = f"{int(age_val_s)}s"
                elif age_val_s < 3600: age_str = f"{int(age_val_s/60)}m"
                else: age_str = f"{int(age_val_s/3600)}h"

                # Check Threshold
                threshold_s = threshold_min * 60
                if age_val_s > threshold_s:
                    if age_val_s > threshold_s * 3 or status != "ok":
                         is_dead = True
                         icon = "🔴"
                    else:
                         is_stale = True
                         icon = "🟡"
                elif status == "ok":
                     icon = "🟢"
                else:
                     icon = "🟡" # ok status but e.g. 'idle'

            except:
                status = "ts_parse_error"
                icon = "⚫️"

        # Table Row
        row = f"{module} | {icon} {status} | {ts_str} | {age_str} | {threshold_min}m | {'yes' if critical else 'no'}"
        monitoring_rows.append(row)
        
        sidecar_entries.append({
            "module": module,
            "status": status,
            "ts_utc": ts_str,
            "age_s": age_val_s,
            "critical": critical
        })

    # Render Block
    ts_gen = now_utc_iso()
    joined_rows = "\n".join(monitoring_rows) or "No targets configured"
    
    block = f"""{MARKER_BEGIN}
### Agent Monitoring
- generated_utc: `{ts_gen}`
- targets: {len(targets)}

{chr(10).join(table_head)}
{joined_rows}

{MARKER_END}"""

    # Update Summary
    if OUTPUT_FILE.exists():
        original = OUTPUT_FILE.read_text(encoding="utf-8")
        if MARKER_BEGIN in original:
            new_content = MARKER_REGEX.sub(block, original)
        else:
            new_content = original.rstrip() + "\n\n" + block + "\n"
        
        try:
            atomic_write(OUTPUT_FILE, new_content)
        except Exception as e:
            fail(3, f"Write failed: {e}")
    else:
        # Policy: If summary missing, maybe minimal write or fail?
        # Spec says: 3 = output write failed.
        # But assumes summary generator exists. We will Create if missing to be safe per idempotency goals?
        # User spec: "Input: existing reports/summary/latest.md (must exist from generator ... fail hard)"
        fail(3, f"Summary file missing: {OUTPUT_FILE}")

    # Sidecar
    try:
        atomic_write(SIDECAR_FILE, json.dumps({
            "ts_utc": ts_gen,
            "targets": sidecar_entries
        }, indent=2) + "\n")
    except Exception as e:
         print(f"WARN: Sidecar write failed: {e}")

    print("OK")
    sys.exit(0)

if __name__ == "__main__":
    main()
