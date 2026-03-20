# Mission Pack: Daily Operator Status Report

**Mission ID prefix:** `daily_status`
**Type:** C — Daily operator health/status report
**Channel:** Telegram → GGMesh (bot: GGMeshV2Bot, chat: -1002324084957)
**Proven:** P7_PROVEN (2026-03-17)

---

## Mission Description

Generates a concise runtime status summary using live evidence from LUKA_RUNTIME_ROOT,
submits it through the governed inference path (Claude → Anthropic), and dispatches
the result to Telegram. Full evidence chain written to observability/artifacts/missions/.

---

## Step 1 — Verify Approval

```bash
LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime python3 -c "
import sys; sys.path.insert(0,'/Users/icmini/0luka')
from tools.ops.approval_state import load_approval_state
s = load_approval_state()
te = s['lanes']['task_execution']
print('task_execution approved:', te['approved_effective'])
print('approved_by:', te.get('approved_by'))
"
```

Expected: `task_execution approved: True`

---

## Step 2 — (If not approved) Approve

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

---

## Step 3 — Execute Mission

```bash
MISSION_ID="daily_status_$(date -u +%Y%m%d)"

dotenvx run --env-file ~/.env -- python3 /Users/icmini/0luka/tools/ops/run_mission.py \
  --prompt "Generate a 3-line executive summary for the 0luka sovereign runtime. Cover: (1) production service status, (2) last inference result, (3) approval state. Be concise." \
  --operator-id boss \
  --mission-id "$MISSION_ID" \
  --notify
```

---

## Step 4 — Retrieve Result

```bash
MISSION_ID="daily_status_$(date -u +%Y%m%d)"

# Full result artifact
cat /Users/icmini/0luka/observability/artifacts/missions/${MISSION_ID}.json | python3 -m json.tool

# Short: just the response
python3 -c "
import json
r = json.load(open('/Users/icmini/0luka/observability/artifacts/missions/${MISSION_ID}.json'))
print('task_id:', r['task_id'])
print('status:', r['status'])
print('response:', r['response'])
print('notify_message_id:', (r.get('notify_result') or {}).get('result', {}).get('message_id'))
"
```

---

## Step 5 — Inspect Evidence

```bash
# Latest operator task evidence
cat /Users/icmini/0luka_runtime/state/operator_task_latest.json | python3 -m json.tool

# Latest inference evidence
cat /Users/icmini/0luka_runtime/state/runtime_governed_inference_latest.json | python3 -m json.tool

# Latest tool dispatch evidence
cat /Users/icmini/0luka_runtime/state/tool_dispatch_latest.json | python3 -m json.tool
```

---

## Step 6 — Check Production Runtime

```bash
launchctl list | grep runtime-sovereign && \
python3 -c "
import json
s = json.load(open('/Users/icmini/0luka_runtime/state/runtime_sovereign_service_latest.json'))
print('pid:', s['pid'], '| tick:', s['tick'], '| ts:', s['ts'])
"
```

---

## Expected Evidence After Run

| File | Expected |
|------|----------|
| `observability/artifacts/missions/daily_status_YYYYMMDD.json` | Full mission artifact |
| `state/operator_task_latest.json` | `status: executed` |
| `state/runtime_governed_inference_latest.json` | `provider: claude`, response present |
| `state/tool_dispatch_latest.json` | `status: executed`, `message_id` non-null |

---

## Variants

### No-notify (silent execution)
```bash
dotenvx run --env-file ~/.env -- python3 /Users/icmini/0luka/tools/ops/run_mission.py \
  --prompt "PROMPT" \
  --operator-id boss
```

### Different provider (if available)
```bash
# Change --provider flag; governed_inference_policy controls which are accepted
dotenvx run --env-file ~/.env -- python3 /Users/icmini/0luka/tools/ops/run_mission.py \
  --prompt "PROMPT" \
  --operator-id boss \
  --provider openai
```
