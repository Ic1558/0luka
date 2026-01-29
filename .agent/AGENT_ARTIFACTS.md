# Agent Artifacts Discovery Contract

> **Purpose**: This file enables any AI agent to discover and use 0luka's agent-generated artifacts.
> **Read this first** before creating implementation plans, tasks, or walkthroughs.

---

## Artifact Locations

### Antigravity (Gemini)
| Type | Path Pattern |
|------|--------------|
| Brain Root | `~/.gemini/antigravity/brain/<conversation-id>/` |
| Task List | `task.md` |
| Implementation Plans | `implementation_plan*.md` |
| Walkthroughs | `walkthrough*.md` |

**Current Session ID**: `e488f23e-d776-4a9f-9782-3e1d4842fc57`

### OpenCode / Claude / Other Agents
| Type | Path |
|------|------|
| Session State | `~/0luka/g/session/SESSION_STATE.md` |
| Handoff | `~/0luka/observability/artifacts/handoff_latest.json` |
| Beacon | `~/0luka/observability/telemetry/global_beacon.jsonl` |

---

## Discovery Protocol

1. **On Session Start**: Read `~/0luka/.agent/AGENT_ARTIFACTS.md` (this file)
2. **Check Active Work**: Read `task.md` from the relevant brain path
3. **Resume Context**: Read last `walkthrough*.md` for completed work summary

---

## Cross-Agent Handoff

When handing off between agents:
1. Write summary to `~/0luka/observability/artifacts/handoff_latest.json`
2. Include: `agent_id`, `ts`, `completed_tasks`, `pending_tasks`, `context_pointers`
3. Next agent reads handoff before starting

---

## Golden Rules

1. **SOT = Files**: Memory is secondary; files are source of truth
2. **Version Control**: All artifacts must be git-trackable (no binary blobs)
3. **No Duplication**: One canonical path per artifact type
4. **Audit Trail**: Every implementation plan has a walkthrough on completion

---

## File Ownership

| Path | Owner | Purpose |
|------|-------|---------|
| `.agent/` | All Agents | Discovery + Policies |
| `g/session/` | Active Session | Runtime state |
| `observability/artifacts/` | System | Telemetry + Handoffs |
| `~/.gemini/antigravity/brain/` | Antigravity | Plans + Tasks |

---

*Last Updated: 2026-01-29*
