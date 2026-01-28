#!/bin/bash

# Raycast Script Command Configuration
# @raycast.schemaVersion 1
# @raycast.title Submit 0luka Task
# @raycast.mode compact
# @raycast.packageName 0luka
# @raycast.icon 🚀
# @raycast.argument1 { "type": "text", "placeholder": "Intent (e.g., system.status)" }
# @raycast.argument2 { "type": "text", "placeholder": "Args JSON (optional)", "optional": true }

# ═══════════════════════════════════════════
# 0luka Unified Task Submitter (Hardened v2)
# ═══════════════════════════════════════════

INTENT="$1"
ARGS="${2:-"{}"}"
ACTOR="raycast"
API_URL="http://127.0.0.1:3004/api/tasks/submit"
TIMEOUT=5

# Robust JSON Submission via Python
python3 -c "
import json, sys, urllib.request, urllib.error, os

def traceparent():
    return f\"00-{os.urandom(16).hex()}-{os.urandom(8).hex()}-01\"

intent = \"$INTENT\"
args_raw = \"\"\"$ARGS\"\"\"
actor = \"$ACTOR\"
api_url = \"$API_URL\"
trace = traceparent()
gates = [\"gate.fs.purity\", \"gate.hash.match\", \"gate.proc.clean\"]

try:
    # Validate Args JSON
    try:
        args_data = json.loads(args_raw)
    except json.JSONDecodeError:
        print(f'❌ Error: Invalid Args JSON format')
        sys.exit(1)

    payload = {
        'intent': intent,
        'actor': actor,
        'args': args_data,
        'verification': {'gates': gates},
        'meta': {'traceparent': trace}
    }
    
    req = urllib.request.Request(
        api_url, 
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'traceparent': trace},
        method='POST'
    )
    
    with urllib.request.urlopen(req, timeout=$TIMEOUT) as response:
        resp_data = json.loads(response.read().decode('utf-8'))
        task_id = resp_data.get('task_id', 'UNKNOWN')
        status = resp_data.get('status', 'QUEUED')
        print(f'🚀 Submitted: {task_id} ({status})')

except urllib.error.URLError as e:
    print(f'❌ Connection Error: {e.reason}')
except Exception as e:
    print(f'❌ System Error: {str(e)}')
"
