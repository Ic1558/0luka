#!/usr/bin/env python3
import subprocess
import json
import sys
import time

MCP_SERVER = "core_brain/ops/mcp_server.py"
PYTHON_EXE = ".venv/bin/python3" # Explicitly use venv python

def send_request(proc, req_data):
    """Send JSON-RPC request and wait for response."""
    proc.stdin.write(json.dumps(req_data) + "\n")
    proc.stdin.flush()
    
    start = time.time()
    while time.time() - start < 5:
        line = proc.stdout.readline()
        if line:
            return json.loads(line)
        time.sleep(0.1)
    return None

def test_power_tools():
    print(f"🚀  Starting MCP Server: {MCP_SERVER}")
    
    try:
        proc = subprocess.Popen(
            [PYTHON_EXE, MCP_SERVER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=0 
        )
    except Exception as e:
        print(f"❌ Failed to start process: {e}")
        sys.exit(1)

    # 1. Initialize
    print("Step 1: Handshaking...")
    init_req = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}
    }
    
    resp = send_request(proc, init_req)
    if not resp or "result" not in resp:
        print(f"❌ Handshake failed: {resp}")
        proc.terminate()
        return

    print("✅ Handshake OK.")
    
    # 2. List Tools
    print("Step 2: Listing Tools...")
    list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    resp = send_request(proc, list_req)
    if resp and "result" in resp:
        tools = [t["name"] for t in resp["result"].get("tools", [])]
        print(f"✅ Found Tools: {tools}")
        
        required = ["system_remedy", "inspect_interface", "distill_notebook_context"]
        missing = [r for r in required if r not in tools]
        if missing:
            print(f"❌ Missing Power Tools: {missing}")
        else:
            print("✅ All Power Tools Registered.")
    
    # 3. Call inspect_interface
    print("Step 3: Calling 'inspect_interface'...")
    call_req = {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "inspect_interface", "arguments": {}}
    }
    resp = send_request(proc, call_req)
    if resp and "result" in resp:
        content = resp["result"].get("content", [{"text": ""}])[0].get("text", "")
        print(f"✅ inspect_interface Output:\n{content[:100]}...") # Truncate
    else:
        print(f"❌ Call failed: {resp}")

    # 4. Call system_remedy (Safe Check)
    print("Step 4: Calling 'system_remedy' (Safe test)...")
    call_req = {
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "system_remedy", "arguments": {"target": "dummy_target"}}
    }
    resp = send_request(proc, call_req)
    if resp and "result" in resp:
        content = resp["result"].get("content", [{"text": ""}])[0].get("text", "")
        print(f"✅ system_remedy Output: {content}")
        if "Unknown remedy target" in content:
            print("✅ Correctly rejected invalid target.")
    
    proc.terminate()

if __name__ == "__main__":
    test_power_tools()
