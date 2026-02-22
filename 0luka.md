# 0luka — System Reference Manual

> **Version**: 1.0 | **Generated**: 2026-02-02 | **Author**: CLC Deep Analysis
> **Mode**: Phase-O (Core Operability Finalization) | **Core Contract**: CLOSED

---

## Executive Summary

**0luka** is a deterministic, governance-driven task orchestration system designed to replace ad-hoc AI agent behavior with structured, auditable automation. It implements a "trust rules + evidence + identity" philosophy over blind AI trust.

### Key Characteristics

- **Architecture**: Compiler → Orchestrator → Execution (Fail-Closed)
- **Philosophy**: "Silent when correct, alarm when wrong"
- **Contract**: Core governance immutable; all changes traceable
- **Mode**: Single-host automation with forensic audit trail

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│              HUMAN (Boss/Owner)                          │
│              (Final Authority)                           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│        INTERFACE LAYER (Raycast/Web)                    │
│    ├─ Approval workflows                                │
│    └─ Task management UI                                │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│         GOVERNANCE LAYER (core_brain)                   │
│    ├─ Policy enforcement (GMX)                          │
│    ├─ Planning (Liam)                                   │
│    └─ Validation (Vera/Codex)                           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│          ORCHESTRATION LAYER (Tools/Bridge)             │
│    ├─ Task routing                                      │
│    ├─ Risk classification (R0-R3)                       │
│    └─ Lane assignment (FAST/APPROVAL/REJECT)            │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│        EXECUTION LAYER (Lisa/Runtime)                   │
│    ├─ Deterministic execution                           │
│    ├─ Evidence collection                               │
│    └─ Forensic logging                                  │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│       VERIFICATION LAYER (Vera/Codex)                   │
│    ├─ Forensic audit                                    │
│    ├─ Evidence validation                               │
│    └─ DONE stamping                                     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│     OBSERVABILITY & AUDIT (Logs/Telemetry)              │
│    ├─ Real-time status                                  │
│    ├─ Incident tracking                                 │
│    └─ Forensic evidence storage                         │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure

```
/Users/icmini/0luka/
├── core/                    # IMMUTABLE - Contract locked
│   ├── governance/          # Laws, policies, ontology
│   ├── router.py            # Policy enforcement
│   ├── policy.yaml          # Actor capabilities
│   ├── kernel/              # Core infrastructure
│   ├── doe/                 # Delegation of Execution
│   ├── verify/              # Gate verification (gates_registry.py)
│   └── catalog_policy.md    # Dry-run gate (≥95 score)
│
├── core_brain/              # READ-ONLY LOCKED (Sovereign)
│   ├── governance/          # Intelligence governance
│   │   ├── agents.md        # Actor definitions (v1.3)
│   │   ├── agent_culture.md # Cultural constitution (v1.1)
│   │   ├── pre_claim_contract.md  # CLEC v1.0
│   │   ├── router.md        # Router protocol
│   │   └── GIT_SAFETY.md    # Git safety rules
│   ├── catalog/             # Skill/tool catalog
│   └── compiler/            # Spec compilation
│
├── interface/               # Execution interface
│   ├── inbox/               # Task ingestion
│   ├── completed/           # Completed tasks
│   ├── schemas/             # Task spec schemas
│   │   ├── clec_v1.yaml     # CLEC schema
│   │   ├── task_spec_v2.yaml
│   │   └── evidence_v1.yaml
│   ├── frontends/           # UI (Raycast CLI)
│   └── web_control_plane/   # Web dashboard
│
├── observability/           # Comprehensive logging
│   ├── telemetry/           # Real-time JSON
│   ├── logs/                # Component logs
│   ├── incidents/           # Incident tracking
│   │   ├── fs_bash_commands.jsonl
│   │   ├── fs_exports.jsonl
│   │   ├── fs_kernel_access.jsonl
│   │   └── tk_incidents.jsonl
│   ├── audit/               # Forensics
│   └── artifacts/           # Evidence storage
│
├── state/                   # System state
│   ├── current_system.json  # Machine state snapshot
│   ├── recent_changes.jsonl # Append-only audit
│   ├── pending.yaml         # Operations queue
│   └── librarian/           # Librarian state
│
├── tools/                   # Operational tooling
│   ├── bridge/              # Task orchestration
│   ├── librarian/           # File organization
│   └── ops/                 # Operations scripts
│
├── skills/                  # Agent skills
│   ├── manifest.md          # Skill registry
│   ├── liam/                # Architect
│   ├── lisa/                # Executor
│   ├── codex/               # Librarian
│   ├── vera/                # Validator
│   └── rio/                 # R&D sandbox
│
├── g/                       # Working memory
│   ├── knowledge/           # MLS ledger, solutions
│   ├── reports/             # Generated reports
│   ├── manuals/             # Tool manuals
│   └── session/             # Session state
│
├── artifacts/               # Task outputs
├── memory/                  # Durable memory
├── runtime/                 # Active execution
├── reports/                 # Human-readable reports
├── logs/                    # Component logs
├── sandbox/                 # Rio sandbox
└── luka.md                  # 30s human dashboard
```

---

## 3. Actor System (Identity Protocol v1.3)

### 3.1 The Five Actors

| Actor | Identity | Role | Capabilities | Restrictions |
|-------|----------|------|--------------|--------------|
| **[GMX]** | Sovereign | Policy, Approval, Strategy | Final authority | No execution |
| **[Liam]** | Architect | Planning, Reasoning (L0-L2) | Writes plans/specs | No git/PR directly |
| **[Lisa]** | Executor | Deterministic Implementation (L3+) | Writes code | NO reasoning, NO git |
| **[Vera]** | Validator | Forensic Audit | Read-only verification | NO execution |
| **[Rio]** | Explorer | R&D, Experiments | Sandbox-only | NO production touch |
| **[Codex]** | Librarian | Documentation, Git Ops | Manages SOT | Review/docs/git only |
| **[Cole]** | Assistant | Hybrid Helper | Long-Run Orchestration | Free/Tracked Modes |

### 3.2 Identity Invariant (Global)

```
Every response MUST begin with the Agent's Call-Sign (e.g., [Liam]).
Violation = Immediate Rejection.
```

### 3.3 Brain Types (Immutable Per Agent)

- **Architect Brain (Liam)**: Abstract, cautious, read-only, refuses ambiguity
- **Executor Brain (Lisa)**: Procedural, deterministic, no interpretation
- **Verifier Brain (Codex)**: Skeptical, evidence-driven, long-context reader
- **Hybrid Brain (Cole)**: Free Mode by default; Tracked Mode only when explicitly requested

---

## 4. Closed-Loop Engineering Contract (CLEC v1.0)

### 4.1 The 5-Stage Loop

Work is "Done" ONLY when passing all stages:

```
1. PLAN:      Intent defined in TaskSpec/PatchPlan
2. APPLY:     File modifications (Atomic)
3. VALIDATE:  Engine verification (Tests/Lint/Build)
4. EVIDENCE:  Forensic recording (Hash/Diff/Log)
5. TRACE:     Backward traceability (Prompt → Author)
```

### 4.2 Pre-Claim Gates (5 Fence-posts)

Before Lisa claims a task:

| Gate | Name | Requirement |
|------|------|-------------|
| G1 | Workspace | Only `/Users/icmini/0luka` allowed |
| G2 | Risk/Lane | Path R0-R3 + Lane validation |
| G3 | Schema | TaskSpec validation against `clec_v1.yaml` |
| G4 | No Secrets | Block on .env/secret detection |
| G5 | Loop Defined | Minimum 1 verification check |

### 4.3 Risk Matrix & Routing

| Level | Name | Paths | Lane | Outcome |
|-------|------|-------|------|---------|
| **R0/R1** | Normal | `modules/`, `reports/`, `tools/`, `docs/` | **FAST** | Auto-Execute |
| **R2** | Governance | `interface/schemas/`, `governance/`, `luka.md` | **APPROVAL** | Hold for Boss |
| **R3** | Kernel/Core | `core/`, `runtime/`, `.env*` | **REJECT** | Hard stop |

---

## 5. Execution Policy

### 5.1 Level Definitions

- **L0 — Trivial**: typo/format/rename, markdown/manuals
- **L1 — Local Patch**: single-file bugfix, logging/errors
- **L2 — Bounded Change**: one-module change, few files
- **L3+ — Complex**: cross-module, architecture change

### 5.2 Who Can Write What

- **Liam**: Level ≤ L2 only (plan + diff + verification)
- **Lisa**: Level ≥ L3 (implementation)
- **Codex**: Review/docs/git/PR management
- **Boss Override**: Explicit in prompt, logged as `BOSS_OVERRIDE=true`

### 5.3 Git Governance

- **Only Codex** authorized for git operations
- Direct-to-main commits **FORBIDDEN**
- All PRs require: `PLAN.md`, `DIFF.md`, `VERIFY.md`
- Branch naming: `feat/<intent>-<id>` or `fix/<intent>-<id>`

---

## 6. Bridge System (Task Orchestration)

### 6.1 Components

| Component | Purpose |
|-----------|---------|
| `bridge_consumer.py` | Event consumption from queue |
| `bridge_task_processor.py` | Task execution pipeline |
| `bridge_dispatch_watchdog.py` | Health monitoring |
| `bridge_watch.zsh` | File system watcher |

### 6.2 Execution Flow

```
Task Emit → Outbox → Bridge Consumer → Dispatcher →
Executor (Lisa) → Evidence → Codex → DONE
```

### 6.3 Telemetry

Real-time status in `observability/telemetry/*.latest.json`:

```json
{
  "ts": "2026-02-01T15:14:03Z",
  "module": "bridge_consumer",
  "status": "ok|error",
  "last_event": {...}
}
```

---

## 7. Librarian System

### 7.1 Purpose

Move scattered files to canonical locations, maintain state invariants.

### 7.2 Forbidden Actions

- Never touch `core/`, `core_brain/`
- Never modify production code (state files only)

### 7.3 Scoring Model (0-100, pass: 70)

| Criterion | Weight | Pass Condition |
|-----------|--------|----------------|
| Path compliance | 30% | Source/dest match rules |
| Checksum discipline | 20% | SHA256 computed |
| Non-core safety | 25% | No core touched |
| Atomicity | 15% | Single move, no partial |
| Traceability | 10% | UTC timestamp + audit |

### 7.4 Canonical Paths

- `reports/summary/latest.md` — Human dashboard
- `state/current_system.json` — Machine state
- `state/recent_changes.jsonl` — Append-only audit
- `luka.md` — 30s quick reference

---

## 8. Observability & Audit

### 8.1 Incident Logs

| Log File | Captures |
|----------|----------|
| `fs_bash_commands.jsonl` | All bash commands |
| `fs_exports.jsonl` | Files exported outside 0luka |
| `fs_kernel_access.jsonl` | Kernel zone access attempts |
| `tk_incidents.jsonl` | Task kernel violations |

### 8.2 Log Rotation

- Component logs: `logs/components/<name>/current.log`
- Daily rotation: `.1`, `.2`, ... `.7`
- Managed by `tools/rotate_logs_min.zsh`

### 8.3 Agent Monitoring

Real-time status in `reports/summary/latest.md`:

```
module | status | last_ts_utc | age | threshold | critical
-------|--------|-------------|-----|-----------|----------
bridge_consumer | ok | ... | 0s | 3m | yes
executor_lisa | ok | ... | 23s | 3m | yes
```

---

## 9. Skill System

### 9.1 Skill Manifest (`skills/manifest.md`)

| Skill | Mandatory Read | Purpose |
|-------|----------------|---------|
| `development` | YES | Codebase evolution & runtime |
| `design` | NO | Design patterns |
| `tailwind-css-expert` | NO | CSS expertise |
| `component-engineer` | NO | Component building |

### 9.2 Skill Catalog Policy

Dry-run gate (scoring 0-100):

- Exact name match: 0-40 points
- Capability match: 0-20 points
- Tag/keyword match: 0-15 points
- Scope & policy safety: 0-10 points
- **Execution threshold**: ≥95 score required

---

## 10. Current System State

### 10.1 Phase-O Objectives

- Paths stable & referenced consistently
- Logs don't grow forever & are auditable
- Summary answers: "what is happening now?"

### 10.2 State Snapshot (`state/current_system.json`)

```json
{
  "ts_utc": "2026-01-30T19:10:07Z",
  "system_mode": "Phase-O",
  "core_status": {
    "core_contract": "closed",
    "core_operability": "in_progress"
  },
  "librarian": {
    "last_score": 100,
    "last_gate": "OK"
  }
}
```

### 10.3 Quick References

| What | Where |
|------|-------|
| Human Dashboard | `luka.md` |
| Machine State | `state/current_system.json` |
| Summary | `reports/summary/latest.md` |
| Telemetry | `observability/telemetry/` |
| Logs | `logs/components/` |

---

## 11. Agent Culture (Constitution v1.1)

### 11.1 Core Principles

1. **Purpose**: Reduce Boss's cognitive load (felt, not claimed)
2. **Brain**: One agent = one brain type (immutable)
3. **Knowledge**: Know the right things, not everything
4. **Memory**: Only inspectable memory retained
5. **Action**: Thinking and acting are separate contracts
6. **Tools**: Explicitly whitelisted, risk-classified
7. **Control**: Delegate, never abdicate
8. **Courage**: Refuse unsafe work
9. **Timing**: Silence is default

### 11.2 Anti-Patterns (Forbidden)

- Long explanations without executable outcome
- "Helpful thoughts" without artifacts
- Guessing missing SOPs
- Assuming Boss intent
- Bypassing gates silently

---

## 12. MLS (Machine Learning Solutions)

### 12.1 Paths

- **Capture Tool**: `tools/mls_capture.zsh`
- **Database**: `g/knowledge/mls_lessons.jsonl`
- **Index**: `g/knowledge/mls_index.json`
- **Reports**: `g/reports/mls/`

### 12.2 What Gets Recorded

- Proven solutions
- Failures and causes
- Patterns and anti-patterns
- Delegation decisions

---

## 13. Design Principles

1. **Traceability (Absolute)**: Every change has reason, plan, evidence
2. **Cleanliness (Obsessive)**: Organization > speed
3. **Cognitive Load Reduction**: Ease human burden
4. **Silence When Correct**: Only speak on decision/failure
5. **Fail-Closed**: Default deny, explicit allow
6. **Deterministic**: Predictable, consistent results
7. **Self-Correcting**: Detect and fix own errors
8. **Evidence-Based**: All work backed by artifacts

---

## 14. Quick Commands

```bash
# View human dashboard
cat luka.md

# View summary
cat reports/summary/latest.md

# Tail bridge consumer log
tail -n 50 logs/components/bridge/current.log

# View system state
cat state/current_system.json

# View recent changes
tail -n 20 state/recent_changes.jsonl

# Check MLS lessons
tail -n 10 g/knowledge/mls_lessons.jsonl
```

---

## 15. Emergency & Safety

### 15.1 Emergency Bypass Policy (v1.0)

- **Allowed host**: `icmini` only
- **Allowed actor**: `[GMX]` only
- **Token**: Single-shot, replay protected

### 15.2 Strictly FORBIDDEN (No Override)

- Path sandbox
- Command whitelist
- Schema validation
- Identity check
- R2/R3 secret scanning

### 15.3 Secret Protection

Blocked patterns:

- `.env` files
- `id_rsa*`, `id_ed25519*`
- `credentials*`, `keychain*`
- `0luka/**/secrets/**`

---

## Changelog

| Date | Version | Change |
|------|---------|--------|
| 2026-02-02 | 1.0 | Initial deep analysis and documentation |

---

> **"Prompt/Intent matters more than raw code — Evidence matters more than words"**
> — CLEC v1.0 Mental Model
