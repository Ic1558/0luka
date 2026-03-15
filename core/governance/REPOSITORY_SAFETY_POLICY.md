# 0LUKA SYSTEM SAFETY POLICY

## Protected Repository & Runtime Topology Rules

**Classification:** 0LUKA Kernel Safety Contract
**Scope:** All agents, tools, scripts, MCP services, and automation processes
**Enforcement:** `core/safety/protected_zone_guard.py` (AG-24)

---

## 1. Protected Zone — Git Repository Metadata

The following paths are **STRICTLY PROTECTED** and must never be modified by automation:

```
.git/
.git/index
.git/objects/
.git/objects/pack/
.git/packed-refs
.git/worktrees/
.git/hooks/
```

Agents, scripts, or tools must **never**:
- delete
- rewrite
- repack
- prune
- move
- directly modify

any file inside these paths.

---

## 2. Forbidden Operations on Live Repository

The following Git maintenance commands must **never** be executed automatically on the canonical repository:

```
git gc
git repack
git prune
git clean -fdx
git worktree prune
git filter-repo
```

These commands are **only allowed** when:
- manual operator maintenance
- explicit operator approval
- isolated maintenance session (not the canonical repo)

---

## 3. Repository Access Model

### Single Writer Policy

Only one process may perform mutating Git operations at a time.

Mutating operations include:
```
git commit  git merge  git reset  git checkout
git add     git rm     git rebase
```

Concurrent writers are **forbidden**.

### Read Operations

Read operations must remain non-invasive:
```
git status  git log  git rev-parse  git show
```

Even read operations must not run concurrently at high frequency from multiple watchers.

---

## 4. Snapshot / Analysis Tools

Snapshot or analysis tools (including Antigravity utilities) must:

- use **read-only** access, OR
- use an **isolated clone/worktree**

Never operate on the canonical live repository.

**Correct model:**
```
canonical repo
      ↓
temporary clone/worktree
      ↓
snapshot / scan / export
```

---

## 5. Runtime Topology Configuration

Changes that may alter system process topology must be **gated** before application.

Gated examples:
- Antigravity MCP config
- Python interpreter path / PYTHONPATH
- launchd services
- agent runtime wiring
- environment variables affecting workers

These changes must not be applied during active runtime without controlled reload procedures.

**Enforcement:** `core/safety/topology_transition_gate.py` (AG-24)

---

## 6. Multi-Agent Access Control

Systems running multiple agents must enforce **repository access coordination**.

Simultaneous uncontrolled access from multiple services is **prohibited**.

Services that must be coordinated:
```
Antigravity       Raycast helpers    MCP servers
launchd workers   bridge watchdog    repository scanners
IDE plugins
```

**Enforcement:** `core/safety/process_concurrency_guard.py` (AG-24)

---

## 7. Incident Severity

Violation of this policy is considered a **HIGH SEVERITY SYSTEM SAFETY BREACH**.

Possible outcomes:
- Git repository corruption
- loss of repository integrity
- runtime topology instability
- uncontrolled agent behavior

---

## 8. Required Preventive Controls

| Control | Implementation |
|---|---|
| Repository Guard | `core/safety/protected_zone_guard.py` — blocks `.git` writes |
| Runtime Health Checks | `git fsck` + `core/safety/runtime_safety_gate.py` |
| Access Coordination | `core/safety/process_concurrency_guard.py` |
| Safe Snapshot Workflow | Isolated clones only — never canonical repo |
| Emergency Stop | `core/safety/emergency_stop.py` — fail-closed |
| Topology Gate | `core/safety/topology_transition_gate.py` — LOCKDOWN/DRAINING modes |
| Autonomy Budget | `core/safety/autonomy_budget.py` — MAX_RETRY=1, MAX_FALLBACK=1 |

---

## 9. Enforcement Scope

This policy applies to:
- AI agents
- automation scripts
- MCP servers
- background services (`sovereign_loop`, `bridge_watchdog`, `ledger_watchdog`)
- developer tooling
- CI/CD helpers

Manual operator actions remain permitted but should follow safe maintenance procedures.

---

## 10. Short Executive Rule

> **No agent, script, MCP tool, or background service may modify `.git` metadata or run Git maintenance commands on the canonical repository.**
>
> **Snapshot and analysis tools must operate on isolated clones or worktrees only.**
>
> **Runtime topology changes must be gated and coordinated to prevent concurrent repository access.**
