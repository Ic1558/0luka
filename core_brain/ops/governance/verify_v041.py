import sys
import os
import time
import json
import struct
import socket
import hashlib
from pathlib import Path

ROOT = Path(os.environ.get("ROOT", str(Path.home() / "0luka"))).expanduser().resolve()
ROOT_STR = str(ROOT)
ROOT_REF = "${ROOT}"
sys.path.append(str(ROOT / "ops/governance"))
try:
    from rpc_client import RPCClient
except ImportError:
    # Fallback if rpc_client not found in path, though PYTHONPATH should handle it
    pass

RPC_SOCK = str(ROOT / "runtime/sock/gate_runner.sock")
BEACON = str(ROOT / "observability/stl/ledger/global_beacon.jsonl")
ONTOLOGY = str(ROOT / "core/governance/ontology.yaml")
HANDLER = str(ROOT / "ops/governance/zen_audit.sh")

def normalize_paths(obj):
    if isinstance(obj, dict):
        return {k: normalize_paths(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_paths(v) for v in obj]
    if isinstance(obj, str):
        return obj.replace(ROOT_STR, ROOT_REF)
    return obj

def test_beacon_chain():
    print("\n== TEST 1: Global Beacon Chain ==")
    rpc = RPCClient()
    # Find a task
    tasks = sorted([f for f in os.listdir(ROOT / "observability/stl/tasks/open") if f.endswith(".yaml")])
    if not tasks:
        print("SKIP: No open tasks")
        return False
    
    t_id = tasks[-1]
    print(f"Running task: {t_id}")
    res = rpc.call("run_task", task_id=t_id)
    if "error" in res:
        print(f"FAIL: {res}")
        return False
        
    # Check Beacon
    if not os.path.exists(BEACON):
        print("FAIL: Beacon file not found")
        return False
        
    with open(BEACON, 'r') as f:
        lines = f.readlines()
        if not lines:
            print("FAIL: Beacon empty")
            return False
        last = json.loads(lines[-1])
        print(f"Last Entry: {normalize_paths(last)}")
        if "prev_beacon_hash" not in last or "this_beacon_hash" not in last:
            print("FAIL: Missing hashes in beacon")
            return False
        # If there was a previous line, check chain
        if len(lines) > 1:
            prev = json.loads(lines[-2])
            if last.get("prev_beacon_hash") != prev.get("this_beacon_hash"):
                print(f"FAIL: Broken Chain! Prev={prev.get('this_beacon_hash')} Link={last.get('prev_beacon_hash')}")
                return False
    
    print("PASS: Beacon Chain Verified")
    return True

def test_frame_cap():
    print("\n== TEST 2: Frame Cap (1MB) ==")
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(RPC_SOCK)
        
        # Craft 1.1MB payload
        payload = b'x' * (1024 * 1024 + 100)
        msg = struct.pack('>I', len(payload)) + payload
        client.sendall(msg)
        
        # Expect disconnect or no response
        client.settimeout(2.0)
        try:
            resp = client.recv(1024)
            print(f"FAIL: Daemon accepted payload, resp len: {len(resp)}")
        except socket.timeout:
            print("PASS: Daemon dropped/ignored oversized frame (Timeout)")
        except ConnectionResetError:
            print("PASS: Daemon closed connection")
    except Exception as e:
        print(f"PASS: Connection failed as expected: {e}")

def get_file_hash(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def test_handler_tamper():
    print("\n== TEST 3: Action Handler Tamper ==")
    rpc = RPCClient()
    
    # 1. Verify clean run
    res = rpc.call("execute_action", task_id="test_id", action_id="action.system.audit")
    if "error" in res:
        print(f"WARN: Initial run error (might be normal if task missing): {res}")
    
    # 2. Tamper
    print(f"Tampering with {HANDLER}...")
    original_content = ""
    with open(HANDLER, 'r') as f:
        original_content = f.read()
        
    try:
        with open(HANDLER, 'a') as f:
            f.write("\n# MALICIOUS")
        
        res = rpc.call("execute_action", task_id="test_id", action_id="action.system.audit")
        if "Handler Tampered" in str(res) or "hash mismatch" in str(res):
            print(f"PASS: Tamper Detected. Res: {res}")
        else:
            print(f"FAIL: Tamper NOT Detected. Res: {res}")
    finally:
        # Restore
        with open(HANDLER, 'w') as f:
            f.write(original_content)

def test_ontology_tamper():
    print("\n== TEST 4: Ontology Tamper ==")
    rpc = RPCClient()
    
    original_content = ""
    with open(ONTOLOGY, 'r') as f:
        original_content = f.read()

    # 1. Tamper Ontology
    print(f"Tampering with {ONTOLOGY}...")
    try:
        with open(ONTOLOGY, 'a') as f:
            f.write("\n# MALICIOUS")
            
        res = rpc.call("verify_gate", gate_id="gate.net.port")
        if "Ontology Tampered" in str(res):
            print(f"PASS: Tamper Detected. Res: {res}")
        else:
            print(f"FAIL: Tamper NOT Detected. Res: {res}")
    finally:
        # Restore
        with open(ONTOLOGY, 'w') as f:
            f.write(original_content)

if __name__ == "__main__":
    if not os.path.exists(RPC_SOCK):
        print(f"FATAL: Socket not found at {RPC_SOCK}")
        exit(1)
        
    test_beacon_chain()
    test_frame_cap()
    test_handler_tamper()
    test_ontology_tamper()
