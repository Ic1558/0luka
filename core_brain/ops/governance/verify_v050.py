import os
import sys
import time
import json
import subprocess
import hashlib
from ops.governance.rpc_client import RPCClient

# v0.5.0 Verification Script
# Updates: Adds Authorize Command Test

RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

ROOT = os.environ.get("ROOT", os.path.expanduser("~/0luka")).rstrip("/")
ROOT_REF = "${ROOT}"

def normalize_paths(obj):
    if isinstance(obj, dict):
        return {k: normalize_paths(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_paths(v) for v in obj]
    if isinstance(obj, str):
        return obj.replace(ROOT, ROOT_REF)
    return obj

def fail(msg):
    print(f"{RED}FAIL: {msg}{RESET}")
    sys.exit(1)

def pass_test(msg):
    print(f"{GREEN}PASS: {msg}{RESET}")

def test_beacon_chain():
    print("\n== TEST 1: Global Beacon Chain ==")
    try:
        with open("observability/stl/ledger/global_beacon.jsonl", "r") as f:
            lines = f.readlines()
            if not lines: fail("Beacon is empty")
            last = json.loads(lines[-1])
            print(f"Last Entry: {normalize_paths(last)}")
            if "this_beacon_hash" not in last: fail("Missing hash chain")
            pass_test("Beacon Chain Verified")
    except Exception as e:
        fail(f"Beacon check failed: {e}")

def test_authorize():
    print("\n== TEST 2: Authorize Command (v0.5.0) ==")
    client = RPCClient()
    
    # 1. Allowed Action
    res = client.call("authorize", action="action.followup.generate", args={})
    if res.get("allowed") is not True:
        fail(f"Authorize refused valid action: {res}")
    pass_test("Authorized valid action")

    # 2. Invalid Action
    res = client.call("authorize", action="action.malicious.destroy", args={})
    if res.get("allowed") is not False:
        fail(f"Authorize allowed invalid action: {res}")
    pass_test("Blocked invalid action")

def test_handler_tamper():
    print("\n== TEST 3: Action Handler Tamper ==")
    # Tamper with a handler
    target = "ops/governance/zen_audit.sh"
    backup = target + ".bak"
    os.rename(target, backup)
    with open(target, "w") as f: f.write("echo 'hacked'")
    os.chmod(target, 0o755)

    try:
        client = RPCClient()
        res = client.call("execute_action", task_id="chk_tamper", action_id="action.system.audit")
        if "Tampered" not in res.get("error", ""):
            fail(f"Tamper check failed: {res}")
        pass_test(f"Tamper Detected. Res: {res}")
    finally:
        os.rename(backup, target) # Restore

def test_ontology_tamper():
    print("\n== TEST 4: Ontology Tamper ==")
    target = "core/governance/ontology.yaml"
    with open(target, "r") as f: orig = f.read()
    
    with open(target, "a") as f: f.write("\n# HACK")
    
    try:
        client = RPCClient()
        res = client.call("verify_gate", gate_id="gate.proc.purity")
        if "Tampered" not in str(res):
            fail(f"Ontology tamper check failed: {res}")
        pass_test(f"Tamper Detected. Res: {res}")
    finally:
         with open(target, "w") as f: f.write(orig)

if __name__ == "__main__":
    if not os.path.exists("ops/governance/rpc_client.py"):
        fail("Run from repo root")
    
    test_beacon_chain()
    test_authorize()
    test_handler_tamper()
    test_ontology_tamper()
