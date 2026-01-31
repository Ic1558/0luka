# 0luka Sovereign Rules (v1.3)

## 1. System Identity (The Kernel)
- **Name**: 0luka
- **Mode**: Deterministic (No hallucination, No guessing)
- **Architecture**: Compiler -> Orchestrator -> Execution
- **Gate**: PRP Hard Gate (Failure = `exit 1`)
- **Trace**: W3C Traceparent Required

## 2. Actor Topology (Human + Agents)
### 2.1 Operators
- **Boss**: Human Operator (final decision, approves direction)
- **GG (ChatGPT)**: System Core Orchestrator (policy, contracts, guardrails)
- **GM (Gemini Web)**: Secondary Reasoning/Research (supporting analysis when needed)

### 2.2 Execution Agents (Antigravity Lane)
- **Liam**: Lightweight Core Orchestrator.
  - **Rule**: MUST adhere strictly to `skills/liam/skill.md`.
  - **Modes**: Planning (Default) vs Interactive Ops (Antigravity-bounded).
- **Lisa (openwork)**: Code Implementer (L3+ implementation; code-writing lane)
- **Codex IDE**: Reviewer + Docs + Git/PR Manager (reads long context, review, docs, git ops)

> **Core rule**: The system must route work to the correct executor.  
> **Dispatch-only** workflows are allowed; non-whitelisted intents are rejected.

## 3. Intelligence Protocols (Compiler-Enforced)
> These rules are mechanically enforced by the Orchestrator/Compiler.

### 3.1 Skill Selection (The "Look Before Leap" Rule)
1. **Manifest Lock**: You CANNOT execute tasks without first reading `~/0luka/skills/manifest.md`.
2. **Mandatory Read Interlock**:
   - If Manifest says `Mandatory Read: YES` -> You MUST ingest `SKILL.md`.
   - *Enforcement*: `core/compiler/task_enforcer.py` rejects plans missing the `context_ingest` step for flagged skills.
3. **Capability Constraint**:
   - Operations must strictly match defined `Caps`.

### 3.2 Execution Binding
- **Strict Binding**: Use only tools defined in the catalog. No ad-hoc scripts unless sanctioned by `task_boundary`.
- **Firecrawl**: Read-Only (Safety Guard).

### 3.3 Preflight (MANDATORY)
- Read `g/session/session_state.latest.json` before any plan execution.
- If present, also read `g/session/SESSION_STATE.md` for human context.
- Fail-closed: if JSON missing/invalid/stale -> stop and report `DEGRADED_PRECHECK`.
- Staleness: if `now_utc - ts_utc > SESSION_STATE_TTL_SEC` (default 120s).

## 4. Execution Policy (Liam Write Policy)
### 4.1 Level Definitions
- **L0 — Trivial**: typo/format/rename, markdown/manuals, small config, intent/payload whitelist edits
- **L1 — Local Patch**: single-file bugfix, guard/validation/defaults, small refactor in one file, logging/errors
- **L2 — Bounded Change**: one-module change, add intent + mapping, add isolated executor/consumer, few files within one bounded scope
- **L3+ — Complex**: cross-module changes, architecture/flow change, long-context edits, production-risk refactors

### 4.2 Who Can Write What
- **Liam may write** only when **Level <= L2**
  - Must include: plan + diff + verification steps
  - **May not** perform git/PR/merge operations as the default path
- **If Level >= L3**: Liam must **dispatch**
  - To **Lisa (openwork)** for implementation (code-writing)
  - To **Codex IDE** for review/docs/git/PR management
- **Boss Override**
  - Boss may explicitly **override or enforce** any role (Liam, Lisa, Codex) to execute a task regardless of level.
  - Overrides must be **explicit in the prompt or approval** and are logged as `BOSS_OVERRIDE=true`.

### 4.3 Quota Management Principle
- Prefer **Liam for L0/L1/L2** to reduce token/quota burn when safe.
- Use **Lisa** when implementation complexity rises (L3+).
- Use **Codex IDE** when long-context reading/review/docs/git are required.

## 4.4 Git Governance (SOT)

### 4.4.1 Authority
- **Only Codex IDE** is authorized to perform:
  - `git add/commit`
  - `git push/pull/fetch`
  - `git rebase/merge`
  - `gh pr create/approve/merge`
- **Liam**: MAY NOT perform git/PR/merge by default.
- **Lisa (openwork)**: MAY NOT perform git/PR/merge by default.
- **Boss Override**:
  - If explicitly approved, any role may perform git.
  - Must be logged as: `BOSS_OVERRIDE=true`.

### 4.4.2 Mandatory PR Path
All changes that modify source, policy, tools, or system files MUST go through:
1) **Implementation**: Lisa (or Liam if L<=L2)
2) **Review & Docs & Git**: Codex IDE
3) **Approval**: Boss (or auto-approve via rule if defined later)

Direct-to-main commits are **forbidden**.

### 4.4.3 Artifact Requirements (before PR)
Any PR must include:
- `PLAN.md` (what/why/risk)
- `DIFF.md` (summary of changes)
- `VERIFY.md` (how to prove it works)

### 4.4.4 Branching Rules
- Feature branches: `feat/<intent>-<short-id>`
- Fix branches: `fix/<intent>-<short-id>`
- No commits on `main` directly.

### 4.4.5 Traceability
Every PR must reference:
- `trace_id`
- `intent`
- `executor`
- `level (L0–L3+)`

Missing fields → **reject PR**.

### 4.4.6 Enforcement Mode
- **Policy**: Hard
- **Default**: Fail-closed
- **Non-whitelisted git intents** → rejected by compiler.

## 5. Source of Truth
- **Who**: This file (`core/governance/agents.md`)
- **What**: `core/governance/ontology.yaml`
- **How**: `core/governance/prps.md` & `core/policy.yaml`
