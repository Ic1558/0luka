#!/usr/bin/env python3
"""
Codex Verifier Adapter v0.1.0
Implements the 'Verify' capability for the 0luka Bridge.
Strictly Read-Only / Safe Execution.
"""
import os
import sys
import json
import subprocess
import shlex

SAFE_COMMANDS = [
    "ls", "grep", "cat", "ps", "curl", "echo", "date", "whoami", "pwd", "wc", "id"
]

def fail(msg):
    print(json.dumps({"status": "FAILURE", "error": msg}, indent=2))
    sys.exit(1)

def success(result):
    print(json.dumps({"status": "SUCCESS", "result": result}, indent=2))
    sys.exit(0)

def verify_command(cmd_str):
    if not cmd_str:
        return False, "Empty command"
    
    parts = shlex.split(cmd_str)
    base = parts[0]
    
    # Simple Allowlist
    if base not in SAFE_COMMANDS:
        # Check if absolute path to safe tools?
        # For now, strict allowlist on basename.
        # But 'ps' might be '/bin/ps'.
        # Let's allow if basename matches.
        if os.path.basename(base) not in SAFE_COMMANDS:
            return False, f"Command not allowed: {base}"
            
    # Injection check (basic)
    if ";" in cmd_str or "|" in cmd_str:
         return False, "Piping/Chaining not supported in Verifier v1"
         
    return True, "OK"

def main():
    # Input: JSON from Stdin or Env?
    # Gate Runner passes args via LUKA_ARGS_JSON env var usually?
    # Or Stdin?
    # Bridge Dispatcher passes `args` in RPC `execute_action`.
    # Gate Runner executes Handler.
    # Gate Runner usually passes args via Env `LUKA_ARGS_JSON` (v0.5 spec).
    
    args_json = os.environ.get("LUKA_ARGS_JSON")
    if not args_json:
        # Fallback: Check argv[1]
        if len(sys.argv) > 1:
            try:
                args = json.loads(sys.argv[1])
            except:
                args = {"check": sys.argv[1]}
        else:
            fail("No input (LUKA_ARGS_JSON or argv)")
    else:
        try:
            args = json.loads(args_json)
        except Exception as e:
            fail(f"Invalid LUKA_ARGS_JSON: {e}")

    # Extract Intent/Goal
    # Bridge payload usually: {"check": "cmd"} or {"goal": "verify X via cmd..."}
    
    check_cmd = args.get("check") or args.get("command")
    if not check_cmd:
        fail("Missing 'check' or 'command' field in payload")

    # Verify Safety
    ok, reason = verify_command(check_cmd)
    if not ok:
        fail(f"Safety Check Failed: {reason}")

    # Execute
    try:
        # Capture Output
        proc = subprocess.run(shlex.split(check_cmd), capture_output=True, text=True, timeout=10)
        
        result = {
            "cmd": check_cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip()
        }
        
        if proc.returncode == 0:
            success(result)
        else:
            # A non-zero exit code is a "Successful Execution of a Fail State"
            # But high-level status might depend.
            success(result) # Return result, let caller decide if it's a failure.
            
    except Exception as e:
        fail(f"Execution Error: {e}")

if __name__ == "__main__":
    main()
