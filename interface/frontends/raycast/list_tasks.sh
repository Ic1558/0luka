#!/bin/bash

# Raycast Script Command Configuration
# @raycast.schemaVersion 1
# @raycast.title List Recent 0luka Tasks
# @raycast.mode fullOutput
# @raycast.packageName 0luka
# @raycast.icon 📋
# @raycast.refreshTime 1m

# ═══════════════════════════════════════════
# 0luka Task Browser (Hardened v2)
# ═══════════════════════════════════════════

API_URL="http://127.0.0.1:3004/api/tasks/list"
TIMEOUT=5

# Robust JSON Parsing via Python
OUTPUT=$(python3 -c "
import json, sys, urllib.request, urllib.error

api_url = \"$API_URL\"

try:
    with urllib.request.urlopen(api_url, timeout=$TIMEOUT) as response:
        data = response.read().decode('utf-8')
        if not data:
            sys.exit(0)
            
        tasks = json.loads(data)
        if not isinstance(tasks, list):
            sys.exit(0)

        print(f'   {\"ID\":<22} | {\"STATUS\":<10} | {\"INTENT\"}')
        print('-' * 70)
        for t in tasks[:15]:
            tid = t.get('task_id', 'N/A')
            status = t.get('status', 'N/A')
            intent = t.get('intent', 'N/A')
            
            # Status indicators
            icon = '🚀'
            if status == 'REJECTED': icon = '❌'
            elif status == 'COMMITTED': icon = '✅'
            elif status in ['FAILED', 'ERROR']: icon = '⚠️'
            
            print(f'{icon} {tid:<20} | {status:<10} | {intent}')

except Exception as e:
    print(f'❌ Error: {str(e)}')
")

echo "$OUTPUT"
echo "$OUTPUT" | pbcopy
