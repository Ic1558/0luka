# Session State Policy

## Rule: session_state != execution permit

`g/session/session_state.latest.json` is a **UI/UX signal only**.

| Signal | Purpose | Blocks execution? |
|--------|---------|-------------------|
| session_state.latest.json | UI readiness indicator | NO (warn-only) |
| dispatcher_heartbeat.json | System liveness (PID check) | Informational |
| dispatch_latest.json | Last dispatch evidence | NO |
| health.py --full | Comprehensive system check | NO (advisory) |

## What session_state IS for
- UI header: Ready / Busy / Stale
- Display mode (agent_active / manual)
- Show last refresh source
- "Last known good snapshot" for UX

## What session_state is NOT for
- Gating task dispatch
- Blocking plan generation
- Permission to execute
- Replacing heartbeat/liveness checks
