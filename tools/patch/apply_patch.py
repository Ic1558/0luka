#!/usr/bin/env python3
import sys
import os
import yaml
import json
import hashlib
import subprocess
import datetime
import shutil
import difflib

# Configuration
EVIDENCE_DIR = "interface/evidence/patches"
SCHEMA_FILE = "interface/schemas/patch_plan.yaml"

def calculate_sha256(filepath):
    """Calculates SHA256 hash of a file."""
    if not os.path.exists(filepath):
        return None
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def apply_diff(filepath, diff_content):
    """Applies a unified diff to a file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Target file for diff not found: {filepath}")
    
    with open(filepath, 'r') as f:
        original_lines = f.readlines()
    
    # Simple diff patching logic is complex to implement robustly from scratch.
    # For now, we will rely on the `patch` command being available, 
    # or simple search/replace if provided in a specific format.
    # HOWEVER, a robust "Applying diff" usually implies `patch` utility.
    
    # Strategy: Write diff to temp file and use `git apply` or `patch`.
    # Git apply is safest if it's a git repo.
    
    tmp_diff_path = filepath + ".patch.tmp"
    with open(tmp_diff_path, 'w') as f:
        f.write(diff_content)
        if not diff_content.endswith('\n'):
            f.write('\n')
            
    try:
        # Try git apply first (safer context handling)
        # --ignore-space-change --ignore-whitespace could be optional args
        cmd = ["git", "apply", "--recount", tmp_diff_path]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode != 0:
            # Fallback or strict error? Strict is better for now.
            raise Exception(f"Patch failed: {result.stderr}")
            
    finally:
        if os.path.exists(tmp_diff_path):
            os.remove(tmp_diff_path)

def ensure_evidence_dir():
    if not os.path.exists(EVIDENCE_DIR):
        os.makedirs(EVIDENCE_DIR)

def document_evidence(plan_path, patch_data, results):
    from datetime import timezone
    ensure_evidence_dir()
    now = datetime.datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%S")
    evi_id = f"EVID-{timestamp}-{os.path.basename(plan_path)}"
    
    evidence = {
        "evidence_id": evi_id,
        "plan_file": plan_path,
        "applied_at_utc": now.isoformat().replace("+00:00", "Z"),
        "author": patch_data.get("author", "unknown"),
        "intent": patch_data.get("intent", ""),
        "results": results
    }
    
    evi_path = os.path.join(EVIDENCE_DIR, f"{evi_id}.json")
    with open(evi_path, "w") as f:
        json.dump(evidence, f, indent=2)
    
    print(f"Evidence recorded: {evi_path}")
    return evi_path

def main():
    if len(sys.argv) < 2:
        print("Usage: apply_patch.py <patch_plan.yaml> [--dry-run]")
        sys.exit(1)

    plan_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if not os.path.exists(plan_path):
        print(f"Error: Plan file not found: {plan_path}")
        sys.exit(1)

    with open(plan_path, 'r') as f:
        try:
            patch = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML: {e}")
            sys.exit(1)

    print(f"Loading PatchPlan: {patch.get('intent', 'No Intent')}")
    print(f"Author: {patch.get('author', 'Unknown')}")
    
    results = []
    success = True

    for change in patch.get("changes", []):
        ctype = change.get("type")
        cfile = change.get("file")
        
        # Safety: No absolute paths, no traversing up
        if cfile.startswith("/") or ".." in cfile:
            print(f"Error: Unsafe path detected: {cfile}")
            success = False
            break
            
        res = {"file": cfile, "type": ctype, "status": "pending"}
        
        try:
            if ctype == "modify":
                if not os.path.exists(cfile):
                    raise FileNotFoundError(f"File to modify not found: {cfile}")
                
                before_hash = calculate_sha256(cfile)
                res["hash_before"] = before_hash
                
                # Pre-flight hash check
                if change.get("hash_check"):
                    if change["hash_check"] != before_hash:
                         raise Exception(f"Hash mismatch! Expected {change['hash_check'][:8]}..., got {before_hash[:8]}...")

                if dry_run:
                    print(f"[DRY-RUN] Would apply diff to {cfile}")
                else:
                    apply_diff(cfile, change["diff"])
                    res["hash_after"] = calculate_sha256(cfile)
                    print(f"[OK] Modified {cfile}")

            elif ctype == "create":
                if os.path.exists(cfile):
                    raise FileExistsError(f"File to create already exists: {cfile}")
                
                if dry_run:
                    print(f"[DRY-RUN] Would create {cfile}")
                else:
                    os.makedirs(os.path.dirname(cfile), exist_ok=True)
                    with open(cfile, 'w') as f:
                        f.write(change["content"])
                    res["hash_after"] = calculate_sha256(cfile)
                    print(f"[OK] Created {cfile}")

            elif ctype == "delete":
                if not os.path.exists(cfile):
                    print(f"[WARN] File to delete not found: {cfile}")
                else:
                    res["hash_before"] = calculate_sha256(cfile)
                    if dry_run:
                        print(f"[DRY-RUN] Would delete {cfile}")
                    else:
                        os.remove(cfile)
                        print(f"[OK] Deleted {cfile}")
            
            res["status"] = "success"
        except Exception as e:
            print(f"[ERROR] Failed to apply to {cfile}: {e}")
            res["status"] = "failed"
            res["error"] = str(e)
            success = False
        
        results.append(res)
        if not success:
            break

    if not dry_run:
        document_evidence(plan_path, patch, results)
        
        # Run verifications
        if success and "verification" in patch:
            print("\nRunning Verification Steps:")
            for step in patch["verification"]:
                cmd = step.get("run")
                print(f"> {cmd}")
                try:
                    subprocess.run(cmd, shell=True, check=True)
                    print("  [PASS]")
                except subprocess.CalledProcessError as e:
                    print(f"  [FAIL] {e}")

if __name__ == "__main__":
    main()
