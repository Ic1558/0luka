# Mission Pack: Recurring / Autonomous Scheduled Missions

**Mission ID prefix:** `scheduled`
**Type:** P10 — Autonomous Scheduling Layer
**Proven:** P10_PROVEN (2026-03-17)

---

## Overview

The mission scheduler runs every 60s via launchd. On each tick it:
1. Loads `LUKA_RUNTIME_ROOT/state/missions_registry.json`
2. For each enabled mission, computes the current window key
3. If `last_run_window != current_window` → dispatches via `run_mission()`
4. Updates `last_run_window` in registry (idempotent)
5. Writes evidence to `state/scheduled_run_latest.json` + `state/scheduled_run_log.jsonl`

---

## Registry Format

**File:** `/Users/icmini/0luka_runtime/state/missions_registry.json`

```json
[
  {
    "mission_id":      "daily_status",
    "schedule":        "daily",
    "prompt":          "Generate a 3-line executive summary for the 0luka runtime.",
    "operator_id":     "boss",
    "provider":        "claude",
    "notify":          true,
    "enabled":         true,
    "last_run_window": null
  }
]
```

**Schedule values:**
| Value | Window key format | Fires once per |
|-------|-------------------|---------------|
| `daily` | `2026-03-17` | Calendar day (UTC) |
| `hourly` | `2026-03-17T14` | Clock hour (UTC) |
| `weekly` | `2026-W12` | ISO week |

---

## Step 1 — Install Scheduler

```bash
# Copy plist to LaunchAgents
cp /Users/icmini/0luka/launchd/com.0luka.mission-scheduler.plist \
   ~/Library/LaunchAgents/

# Load
launchctl load ~/Library/LaunchAgents/com.0luka.mission-scheduler.plist

# Verify loaded (exit code 0, no error)
launchctl list | grep mission-scheduler
```

---

## Step 2 — Register a Mission

```python
import sys; sys.path.insert(0, '/Users/icmini/0luka')
import os; os.environ['LUKA_RUNTIME_ROOT'] = '/Users/icmini/0luka_runtime'

from runtime.mission_scheduler import upsert_mission

upsert_mission({
    "mission_id":      "daily_status",
    "schedule":        "daily",
    "prompt":          "Generate a 3-line executive summary for the 0luka sovereign runtime. Cover: (1) production service status, (2) last inference result, (3) approval state.",
    "operator_id":     "boss",
    "provider":        "claude",
    "notify":          True,
    "enabled":         True,
    "last_run_window": None,
})
print("registered")
```

Or via shell (one-liner):
```bash
LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime dotenvx run --env-file ~/.env -- \
  python3 -c "
import sys; sys.path.insert(0,'/Users/icmini/0luka')
from runtime.mission_scheduler import upsert_mission
upsert_mission({'mission_id':'daily_status','schedule':'daily','prompt':'3-line exec summary for 0luka runtime','operator_id':'boss','provider':'claude','notify':True,'enabled':True,'last_run_window':None})
print('registered')
"
```

---

## Step 3 — Manual Tick (test before scheduler fires)

```bash
LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime dotenvx run --env-file ~/.env -- \
  python3 /Users/icmini/0luka/runtime/mission_scheduler.py
```

Expected output:
```json
{
  "tick_ts": "2026-03-17T...",
  "dispatched": 1,
  "results": [
    {
      "mission_id": "daily_status",
      "window": "2026-03-17",
      "status": "executed",
      "task_id": "op_..."
    }
  ]
}
```

Running again in the same window → `"dispatched": 0` (idempotent).

---

## Step 4 — Inspect Evidence

```bash
# Latest scheduled run
cat /Users/icmini/0luka_runtime/state/scheduled_run_latest.json | python3 -m json.tool

# Full run log
tail -5 /Users/icmini/0luka_runtime/state/scheduled_run_log.jsonl | python3 -m json.tool

# Mission artifact
cat /Users/icmini/0luka/observability/artifacts/missions/daily_status_2026-03-17.json | python3 -m json.tool
```

---

## Step 5 — Enable / Disable a Mission

```python
from runtime.mission_scheduler import load_registry, save_registry

missions = load_registry()
for m in missions:
    if m['mission_id'] == 'daily_status':
        m['enabled'] = False   # or True to re-enable
save_registry(missions)
```

---

## Step 6 — Reset Window (force re-run today)

```python
from runtime.mission_scheduler import load_registry, save_registry

missions = load_registry()
for m in missions:
    if m['mission_id'] == 'daily_status':
        m['last_run_window'] = None
save_registry(missions)
# Next tick will re-dispatch
```

---

## Scheduler Logs

```bash
# stdout (tick output)
tail -f /Users/icmini/0luka_runtime/logs/mission_scheduler.stdout.log

# stderr (import/runtime errors)
tail -f /Users/icmini/0luka_runtime/logs/mission_scheduler.stderr.log
```

---

## Expected Evidence After Run

| File | Expected |
|------|----------|
| `state/missions_registry.json` | `last_run_window` updated for dispatched missions |
| `state/scheduled_run_latest.json` | `status: executed`, `window` = current window |
| `state/scheduled_run_log.jsonl` | One record per dispatch |
| `observability/artifacts/missions/<id>_<window>.json` | Full mission artifact |
