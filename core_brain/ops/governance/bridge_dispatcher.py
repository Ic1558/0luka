#!/usr/bin/env python3
"""
Bridge Dispatcher (Universal) v0.1.0
Watches observability/bridge/inbox/ for tasks.
Routes intents to Gate Runner actions.
"""
import os
import sys
import json
import time
import shutil
import socket
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOME = Path(os.environ.get("HOME", "/Users/icmini"))
if str(ROOT).startswith("/Users/icmini/0luka/core_brain"):
    # Adjusted for core_brain location
    ROOT = HOME / "0luka"

INBOX_DIR = ROOT / "observability/bridge/inbox"
ARCHIVE_DIR = ROOT / "observability/bridge/archive"
GATE_SOCK = ROOT / "runtime/sock/gate_runner.sock"

# Intent -> Action Map
ROUTING_TABLE = {
    "plan": "action.plan",
    "verify": "action.verify"
}

def send_rpc(payload):
    if not GATE_SOCK.exists():
        print(f"[ERR] Gate Runner socket not found: {GATE_SOCK}")
        return None
    
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(GATE_SOCK))
        
        frame = json.dumps(payload).encode()
        client.sendall(struct.pack('>I', len(frame)) + frame)
        
        len_bytes = b''
        while len(len_bytes) < 4:
            chunk = client.recv(4 - len(len_bytes))
            if not chunk: break
            len_bytes += chunk
            
        if len(len_bytes) < 4:
            return None
            
        msg_len = struct.unpack('>I', len_bytes)[0]
        data = b''
        while len(data) < msg_len:
            chunk = client.recv(min(4096, msg_len - len(data)))
            if not chunk: break
            data += chunk
            
        return json.loads(data.decode())
        
    except Exception as e:
        print(f"[ERR] RPC Failed: {e}")
        return None
    finally:
        client.close()

def process_task(task_path):
    try:
        with open(task_path, 'r') as f:
            task = json.load(f)
        
        intent = task.get("intent")
        task_id = task.get("task_id", "unknown")
        
        if intent in ROUTING_TABLE:
            action = ROUTING_TABLE[intent]
            print(f"[INFO] Routing {task_id} :: {intent} -> {action}")
            
            # Call Gate Runner
            # We use 'authorize' first? Or 'execute_action'?
            # Let's use execute_action directly as we are a trusted dispatcher.
            
            payload = {
                "cmd": "execute_action",
                "task_id": task_id,
                "action_id": action,
                "args": task.get("payload", {}),
                "client_id": "bridge_dispatcher",
                "client_path": str(Path(__file__).resolve()) 
                # Note: gate_runner checks client_path for authorized mutants, 
                # but execute_action is usually open for local trusted execution?
                # Actually, gate_runner doesn't strictly validate client_path for 'execute_action', only 'authorized_mutation'.
            }
            
            resp = send_rpc(payload)
            print(f"[RES ] {resp}")
            
        else:
            print(f"[SKIP] Unknown intent: {intent}")
            
        # Archive
        archive_path = ARCHIVE_DIR / task_path.parent.name
        archive_path.mkdir(parents=True, exist_ok=True)
        shutil.move(str(task_path), str(archive_path / task_path.name))
        
    except Exception as e:
        print(f"[ERR ] Failed processing {task_path}: {e}")

def main():
    if not INBOX_DIR.exists():
        print(f"[WAIT] Inbox missing: {INBOX_DIR}")
        return

    print(f"[DEBUG] Scanning {INBOX_DIR} for **/*.task.json")
    # Scan recursive
    files = list(INBOX_DIR.glob("**/*.task.json"))
    print(f"[DEBUG] Found {len(files)} tasks: {[f.name for f in files]}")

    for path in files:
        process_task(path)

if __name__ == "__main__":
    main()
