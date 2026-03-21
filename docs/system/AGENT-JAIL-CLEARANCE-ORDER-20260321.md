# GG Orchestrator Directive — Agent Jail Clearance Order
**Issued:** 2026-03-21
**Authority:** GG (Orchestrator / Governance)
**Scope:** All 5 agents — CLC, Codex, GMX, GG, Gemini
**Status:** LOCKED — do not edit without GG override

---

## Shared System Summary (GG → All Agents)

**Current state as of 2026-03-21:**

- All-5 Agent Mailbox Runtime v1 is SHIPPED and PROVEN (2-hop CLC↔Codex chain confirmed)
- `watcher_core.zsh` is the shared runtime core — PR #415 + PR #416 merged to main
- One-open-lane discipline is in effect across all 5 agents
- `additionalDirectories` for `_AI_INBOX` configured in `~/.claude/settings.json` — requires session restart to activate
- Typhoon OCR A/B/C lane WO issued to Codex — in queue
- Trust boundary config WO queued after OCR WO closes

**Known open blockers:**

| # | Blocker | Owner |
|---|---------|-------|
| A | `scan_backlog` blindspot — 18+ file types invisible to watcher | CLC |
| B | `INBOUND-INFORM` verdict not yet in `watcher_core.zsh` | CLC |
| C | `additionalDirectories` not active until session restart | Boss |
| D | Trust boundary config (sandbox write access) | Codex |
| E | `clc_result_handler.zsh` — generalize beyond exact trigger | CLC (after D) |

---

## GG Directive — Agent Decision Lock

### CLC

**CURRENT JAIL:**
1. `scan_backlog` misses 18+ file types — INBOUND-RESULT verdict never fires for HELD/BLOCKED/MASTER/AUDIT/REPORT files
2. Pre-compact report rule was "after" — now corrected to "BEFORE" but enforcement is self-discipline only
3. Rule C violation — memory/config edits inline with operational reply (twice)
4. `clc_result_handler.zsh` — exact trigger only; general result processing not yet built
5. `additionalDirectories` not active — Write/Read on `_AI_INBOX` still prompts in active session
6. Originator-response gap — CLC writes ACK to outbox but does not drop to originator inbox

**DECISION MODE:** EXECUTE (for locked zones) / DELEGATE (for non-locked)

**NEXT REQUIRED ACTION:**
1. Write this system doc to repo (current task)
2. Task A: extend `scan_backlog` + INBOUND-INFORM verdict — PR to main
3. Task B: write locked rules into CLAUDE.md (auto-inbox-check, pre-compact, originator-response, Rule C)

**WHAT CLC MUST NOT DO:**
- Edit memory or config in the same turn as an operational reply (Rule C)
- Claim autonomous overnight operation proven — only 1-human-drop 4-step chain is proven
- Touch GMX-owned files: `kernel_frozen_manifest.yaml`, `gate_layer_separation.py`, `activity_feed_linter.py`, `core/activity_feed_guard.py`

**STATUS:** CLEARANCE-A-ACTIVE (executing jail clearance order)

---

### Codex

**CURRENT JAIL:**
1. Trust boundary not configured — can't write to `_AI_INBOX` (GD path) from headless execution
2. `codex exec --ephemeral` non-TTY issues — known GitHub issues (#4219, #1340, #1208, #1080)
3. Auth fragility in headless mode (#3820, #1976)
4. No fallback to `run_mission.py` (codex not a supported provider in `governed_inference_policy.py`)

**DECISION MODE:** EXECUTE (within WO scope, codex/inbox only)

**NEXT REQUIRED ACTION:**
- Execute OCR lane WO (`WO-CLC-TYPHOON-OCR-IMPLEMENT_20260321.md`)
- Execute trust boundary config WO when unqueued

**WHAT CODEX MUST NOT DO:**
- Auto-expand WO scope
- Write results directly to other agent inboxes without CLC relay
- Use `run_mission.py --provider codex`

**STATUS:** CLEARANCE-B-PENDING-WO

---

### GMX

**CURRENT JAIL:**
1. v1 authority = terminal non-executing only — may only write `HELD-GMX-*.md` + `.done`
2. No auto-execution, no WO forwarding, no acceptance
3. Emergency git/config ops authority not yet settled

**DECISION MODE:** HOLD-AND-RETURN (write HELD + .done, no execution)

**NEXT REQUIRED ACTION:**
- Acknowledge this directive
- Return any queued items as HELD until authority negotiation resolves

**WHAT GMX MUST NOT DO:**
- Accept or plan WOs in v1
- Take autonomous git/config actions without Boss approval

**STATUS:** CLEARANCE-C-PENDING-AUTHORITY-NEGOTIATION

---

### GG

**CURRENT JAIL:**
1. Not a local always-on autonomous runtime executor in v1
2. Governance-visible/orchestrator role — not operational executor
3. Can issue directives but cannot auto-execute or forward WOs

**DECISION MODE:** ORCHESTRATE (directives, governance audits, system-state notices)

**NEXT REQUIRED ACTION:**
- Acknowledge directive is recorded
- No further action until next governance trigger

**WHAT GG MUST NOT DO:**
- Auto-execute WOs
- Override terminal agent states (HELD/BLOCKED-GG are final)
- Operate as runtime executor in v1

**STATUS:** CLEARANCE-D-ACKNOWLEDGED (issuer of this directive)

---

### Gemini

**CURRENT JAIL:**
1. Execution path unproven — headless `gemini -p` works but result routing untested end-to-end
2. Trust boundary not configured — same GD path write problem as Codex
3. No direct execution authority — bounded worker only, results returned to CLC for review before acting

**DECISION MODE:** BOUNDED-WORKER (process explicit worker WOs, return to CLC inbox)

**NEXT REQUIRED ACTION:**
- Parked until Codex trust boundary fix is proven
- Then re-prove `gemini_invoke.zsh` end-to-end

**WHAT GEMINI MUST NOT DO:**
- Take direct execution actions on repo
- Forward results to non-CLC inboxes
- Act without explicit WO

**STATUS:** CLEARANCE-E-PARKED-PENDING-D

---

## Clearance Execution Order

```
A → B → C → D → E

A: CLC scan_backlog + INBOUND-INFORM (Task A)
B: CLAUDE.md locked rules (Task B)
C: Session restart → additionalDirectories active
D: Codex trust boundary config
E: CLC clc_result_handler.zsh generalize
```

Each stage gates the next. No parallel execution across stages that depend on each other.

---

## Shared Workflow Law (locked by GG)

| Case | Rule |
|------|------|
| Routine / clear / scoped / low-risk | EXECUTE NOW |
| Artifact drop (WO, RESULT, ACK) | SEND NOW |
| Ambiguous / risky / 4+ dependency layers | PLAN ONLY |
| Out-of-scope expansion | BLOCK immediately |

---

## Invariants Locked by This Directive

1. **`.done` is the universal terminal dedup marker** — any WO with `.done` is permanently skipped
2. **`.accepted` is strictly execution-only** — PLAN-ONLY never writes `.accepted`
3. **GMX and GG are terminal non-executing** — `is_terminal_agent()` in `watcher_core.zsh` enforces this
4. **One open lane per agent** — `.accepted` or `.planned` without `.done` = lane locked
5. **No side-lane expansion** — watcher writes `.queued` for second WO, does not execute
6. **Originator response required** — every CLC output drops to originator inbox; `clc/outbox` ACK ≠ delivery
7. **Pre-compact report BEFORE compact** — not after; retroactive is acceptable only when auto-compact fires without warning
8. **Rule C: no memory/config edits inline with operational reply** — separate turn required

---

*This document is a system record committed to the 0luka repo. It is not operational code.*
*Do not delete. Do not move. Can be superseded by a new GG directive with explicit version bump.*
