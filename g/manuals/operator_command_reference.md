# Sovereign 0luka Runtime — Operator Command Reference

**Runtime root:** `/Users/icmini/0luka_runtime`
**Repo:** `/Users/icmini/0luka`
**Env file:** `/Users/icmini/.env` (dotenvx-managed)
**Proven state:** P0…P6_PROVEN (2026-03-17)

---

## 0. Environment Prerequisites

All execution commands require dotenvx to inject API keys:

```bash
# Verify env loads correctly
dotenvx run --env-file ~/.env -- python3 -c "import os; print(os.environ.get('ANTHROPIC_API_KEY','MISSING')[:20])"

# Verify approval is active
LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime python3 -c "
from tools.ops.approval_state import load_approval_state
import json, sys; sys.path.insert(0,'/Users/icmini/0luka')
s = load_approval_state()
print('task_execution:', s['lanes']['task_execution']['approved_effective'])
"
```

---

## 1. Submit Operator Task

```bash
dotenvx run --env-file ~/.env -- python3 -c "
import sys, os; sys.path.insert(0, '/Users/icmini/0luka')
os.environ['LUKA_RUNTIME_ROOT'] = '/Users/icmini/0luka_runtime'
from runtime.operator_task import submit_operator_task
result = submit_operator_task(
    prompt='YOUR_PROMPT_HERE',
    operator_id='boss',
    provider='claude',
)
import json; print(json.dumps(result, indent=2))
"
```

**Returns:** `task_id`, `status` (executed|blocked), `inference_id`, `response`

---

## 2. Approve task_execution Lane

```bash
LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime python3 -c "
import sys; sys.path.insert(0, '/Users/icmini/0luka')
from tools.ops.approval_state import write_approval_state
from datetime import datetime, timezone
write_approval_state({
    'task_execution': {
        'approved': True,
        'approved_by': 'boss',
        'approved_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'expires_at': None,
    }
})
print('approved')
"
```

**To expire/revoke:**
```bash
LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime python3 -c "
import sys; sys.path.insert(0, '/Users/icmini/0luka')
from tools.ops.approval_state import write_approval_state
write_approval_state({'task_execution': {'approved': False, 'approved_by': 'boss', 'approved_at': None, 'expires_at': None}})
print('revoked')
"
```

---

## 3. Execute Task (Submit + Dispatch Tool in One)

```bash
dotenvx run --env-file ~/.env -- python3 /Users/icmini/0luka/tools/ops/run_mission.py \
  --prompt "YOUR_PROMPT" \
  --operator-id boss \
  --notify
```

`--notify` dispatches the result to Telegram (GGMESH channel).

---

## 4. Inspect Latest Result

```bash
# Latest operator task
cat /Users/icmini/0luka_runtime/state/operator_task_latest.json | python3 -m json.tool

# Latest inference record
cat /Users/icmini/0luka_runtime/state/runtime_governed_inference_latest.json | python3 -m json.tool

# Latest tool dispatch
cat /Users/icmini/0luka_runtime/state/tool_dispatch_latest.json | python3 -m json.tool
```

---

## 5. Inspect Evidence (Full Logs)

```bash
# All operator tasks (chronological)
tail -20 /Users/icmini/0luka_runtime/state/operator_task_log.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    print(r['ts_submitted'], r['task_id'], r['status'], repr((r.get('response') or '')[:60]))
"

# All inference requests
tail -10 /Users/icmini/0luka_runtime/state/runtime_governed_inference_log.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    print(r['ts_routed'], r['inference_id'][:8], r['provider'], repr((r.get('response') or '')[:60]))
"

# All tool dispatches
tail -10 /Users/icmini/0luka_runtime/state/tool_dispatch_log.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    print(r['ts_dispatched'], r['tool_name'], r['status'], r.get('result', {}).get('message_id'))
"
```

---

## 6. Production Runtime Health

```bash
# Service status + last heartbeat
launchctl list | grep runtime-sovereign && \
cat /Users/icmini/0luka_runtime/state/runtime_sovereign_service_latest.json | python3 -m json.tool

# Last N heartbeat ticks
tail -5 /Users/icmini/0luka_runtime/state/runtime_sovereign_service_log.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    if 'tick' in r:
        print(f\"tick={r['tick']} pid={r['pid']} ts={r['ts']}\")
"
```

---

## 7. Stop / Start / Check Production Service

```bash
# Start (idempotent)
launchctl load ~/Library/LaunchAgents/com.0luka.runtime-sovereign.plist

# Stop
launchctl unload ~/Library/LaunchAgents/com.0luka.runtime-sovereign.plist

# Check (PID + last exit status + label)
launchctl list | grep runtime-sovereign

# Full job state
launchctl print gui/$(id -u)/com.0luka.runtime-sovereign 2>/dev/null || launchctl list | grep runtime-sovereign
```

---

## 8. Quick Health Summary

```bash
LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime python3 -c "
import sys, json; sys.path.insert(0, '/Users/icmini/0luka')
from pathlib import Path
sd = Path('/Users/icmini/0luka_runtime/state')
svc = json.loads((sd / 'runtime_sovereign_service_latest.json').read_text())
task = json.loads((sd / 'operator_task_latest.json').read_text()) if (sd / 'operator_task_latest.json').exists() else {}
inf  = json.loads((sd / 'runtime_governed_inference_latest.json').read_text()) if (sd / 'runtime_governed_inference_latest.json').exists() else {}
print('service  :', svc.get('supervisor_status'), 'tick', svc.get('tick'), 'pid', svc.get('pid'))
print('last task:', task.get('status'), task.get('task_id','—')[:24])
print('last inf :', inf.get('provider'), inf.get('ts_routed','—')[:19])
from tools.ops.approval_state import load_approval_state
ap = load_approval_state()
print('approval :', ap['lanes']['task_execution'].get('approved_effective'))
"
```

---

## Evidence Files Reference

| File | Contents |
|------|----------|
| `state/operator_task_latest.json` | Last operator task (result + response) |
| `state/operator_task_log.jsonl` | All operator tasks |
| `state/runtime_governed_inference_latest.json` | Last inference record |
| `state/runtime_governed_inference_log.jsonl` | All inference records |
| `state/tool_dispatch_latest.json` | Last tool dispatch |
| `state/tool_dispatch_log.jsonl` | All tool dispatches |
| `state/runtime_sovereign_service_latest.json` | Last heartbeat tick |
| `state/runtime_sovereign_service_log.jsonl` | All heartbeat ticks + startups/shutdowns |
| `state/approval_state.json` | Current lane approvals |
