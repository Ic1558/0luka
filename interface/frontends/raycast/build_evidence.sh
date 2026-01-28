#!/bin/bash

# Raycast Script Command Configuration
# @raycast.schemaVersion 1
# @raycast.title 0luka: Build Evidence Pack
# @raycast.mode compact
# @raycast.packageName 0luka
# @raycast.icon 🛡️

# ═══════════════════════════════════════════
# 0luka Evidence Pack Automation (Hardened)
# ═══════════════════════════════════════════

INTENT="action.audit.evidence_pack"
ARGS='{"priority": "high"}'
ACTOR="raycast"
API_URL="http://127.0.0.1:3004/api/tasks/submit"
TIMEOUT=10

RESULT=$(python3 -c "
import json, sys, urllib.request, urllib.error, os

def traceparent():
    return f\"00-{os.urandom(16).hex()}-{os.urandom(8).hex()}-01\"

intent = \"$INTENT\"
args_raw = '''$ARGS'''
actor = \"$ACTOR\"
api_url = \"$API_URL\"
trace = traceparent()
gates = [\"gate.fs.purity\", \"gate.hash.match\", \"gate.proc.clean\"]

try:
    args_data = json.loads(args_raw)
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
        print(f'{task_id}')

except Exception as e:
    print(f'ERROR: {str(e)}')
")

if [[ $RESULT == TASK-* ]]; then
    echo "🛡️ Audit Triggered: $RESULT"
    echo "$RESULT" | pbcopy
else
    echo "❌ $RESULT"
fi
