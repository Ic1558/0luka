# ADR-GIT-001: Git Safety Rules for the 0luka Canonical Repository

**Status:** ACCEPTED
**Date:** 2026-03-16
**Authors:** CLC (post-incident, Git corruption 2026-03-15)
**Replaces:** none

---

## Context

On 2026-03-15/16, the 0luka local Git object store was corrupted and the
entire `.git/` directory was lost. Root cause: Liam's Antigravity-side
integration fix (Python interpreter path, MCP config, duplicate plist
creation) destabilized the process topology, producing a sustained crash-loop
(KeepAlive=true, 3 s restart interval) with concurrent filesystem access
to Git-adjacent paths. The dispatcher entered a 207-cycle rapid-retry loop,
and `feed_sha_mismatch` events cascaded from concurrent state mutations.

Recovery required a fresh GitHub clone. All data was preserved because HEAD
(`31d0d51`) was already pushed. The incident was recoverable only because of
this pre-existing GitHub backup.

**Immediate risks that enabled the incident:**
1. `tools/run_tool.zsh` had `git add .` + `git commit` automatable by any agent
2. No guard prevented dangerous maintenance commands (`git gc`, `git repack`, etc.)
3. No documented rule required isolated clones for snapshot/analysis tools
4. Antigravity topology changes had no approval gate

---

## Decision

### Rule 1 — No automation may invoke `git add .` or `git add -A` against the live repo

Automated `git add .` mass-stages all working tree files, including files
currently being written by concurrent processes. Under high-concurrency
conditions this can corrupt `.git/index`.

**Enforcement:** `tools/run_tool.zsh` `save` verb is permanently blocked.
All artifact persistence uses `save_now.zsh` (artifact-only, no git writes).

### Rule 2 — Forbidden maintenance commands on the live canonical repo

The following commands **must never** run against `/Users/icmini/0luka`:

```
git gc
git repack
git prune
git clean -fdx (or -f, -fd)
git worktree prune
git filter-repo
git filter-branch
git fsck       (read-only but heavy — requires explicit operator approval)
```

If maintenance is genuinely needed, it **must** operate on an isolated clone:
```bash
git clone /Users/icmini/0luka /tmp/0luka-maintenance-$(date +%Y%m%d)
cd /tmp/0luka-maintenance-*/
git gc      # safe here — isolated clone only
```

**Enforcement:** `tools/ops/git_safety_guard.py --scan` detects these in
active automation code and exits non-zero.

### Rule 3 — Protected Git metadata paths

The following paths are **read-only** for all automation. No script, agent,
or launchd service may delete, rename, move, or directly overwrite them:

```
.git/
.git/objects/
.git/objects/pack/
.git/index
.git/packed-refs
.git/worktrees/
.git/hooks/
.git/config
.git/HEAD
```

Direct manipulation of these paths (via `rm`, `shutil.rmtree`, `os.rename`,
`mv`) is forbidden in automation code. Any operation on these paths must be
a standard `git` command invoked through the Git CLI with appropriate locks.

**Enforcement:** `tools/ops/git_safety_guard.py --scan` flags destructive
operations targeting `.git/` subpaths.

### Rule 4 — Single-writer expectation for the working tree

Git assumes a single-writer model for the working tree and index. When
multiple processes write to working tree files simultaneously:
- `.git/index.lock` contention causes commit/status failures
- Pack file writes from background tools (snapshot managers, IDE integrations)
  can corrupt in-progress pack operations

**Required behavior:**
- Automation that writes to the working tree must hold a lock (`flock` or
  an application-level lock file) before modifying files under ROOT.
- Background services must not write to ROOT while a dispatcher cycle is
  active (`LUKA_RUNTIME_ROOT/locks/dispatcher.lock`).

### Rule 5 — Antigravity and MCP topology changes require explicit approval

The 2026-03-15 incident was triggered by an Antigravity-side integration
change (Python interpreter path, duplicate plist creation) made without
verifying the process topology impact on the live repo.

**Required before any change to:**
- `/Users/icmini/Library/LaunchAgents/com.antigravity.*.plist`
- `/Users/icmini/Library/LaunchAgents/com.0luka.*.plist`
- `modules/antigravity/` interpreter paths or PYTHONPATH settings
- Any MCP server config that spawns background git operations

**Approval gate:**
1. Verify no duplicate plists exist for the same `ProgramArguments` target
2. Verify all KeepAlive plists have correct PYTHONPATH and no ModuleNotFoundError
3. Run `python3 core/health.py --full` after plist reload
4. Explicitly document the change in the commit message

### Rule 6 — Snapshot and export tools must use isolated clones

Tools that read git history for snapshot, export, analysis, or MCP ingestion
(e.g., opencode snapshot, `build_sot_pack.py`, `publish_notebooklm.py`) must:
- Operate on a separate clone at a non-canonical path, OR
- Be strictly read-only (no pack operations, no gc, no index writes)

If a tool cannot guarantee read-only operation, it must clone first.

---

## Protected Repository Metadata (summary table)

| Path | Protection Level | Permitted operations |
|------|-----------------|----------------------|
| `.git/objects/pack/` | CRITICAL | Read by git CLI only |
| `.git/index` | CRITICAL | Written by git CLI only; never direct file write |
| `.git/packed-refs` | HIGH | Written by git CLI only |
| `.git/config` | HIGH | Written by git config only |
| `.git/worktrees/` | HIGH | Managed by git worktree only |
| `.git/hooks/` | MEDIUM | Read-only for installed hooks; managed by `.githooks/` |
| `.git/HEAD` | HIGH | Written by git checkout/branch only |

---

## Consequences

**Positive:**
- Automated `git add .` is permanently blocked (primary corruption risk removed)
- `git_safety_guard.py --scan` detectable in CI/pre-claim gate
- Antigravity topology changes have a documented approval gate
- Isolated clone requirement for maintenance prevents live repo gc

**Negative:**
- `run_tool.zsh save` verb is broken for any callers — they must migrate to
  `save_now.zsh`. (Audit: grep for `run_tool.zsh save` or `run_tool save`)
- Operators who relied on automated commit must use explicit `git add <file>`
  + `git commit` from a human terminal session

---

## Enforcement

| Mechanism | What it catches |
|-----------|----------------|
| `tools/ops/git_safety_guard.py --scan` | Forbidden maintenance commands, destructive .git path ops |
| `tools/run_tool.zsh` blocked `save` verb | Automated mass-stage prevention |
| `.githooks/pre-commit` (existing) | Large file blocking, artifact directory blocking |
| This ADR | Topology change approval gate (manual, policy-enforced) |

To add to pre-claim gate:
```bash
# In tools/ops/pre_claim_gate.zsh, add:
python3 tools/ops/git_safety_guard.py --scan || exit 1
```

---

## Incident Closure — 2026-03-16

**Confirmed deletion mechanism (shell session evidence):**

Session `0A764B8A` (Mar 13, Bangkok time) contains:
```
cd /Users/icmini/0luka
git show 0luka-runtime-v1
git diff 0luka-runtime-v1
git reset --hard 0luka-runtime-v1 && git clean -fdx   ← deletion event
```

`git clean -fdx` executed from `/Users/icmini/0luka` deleted all untracked files
including `repos/option/modules/antigravity/realtime/control_tower.py`.
The file was untracked (never committed) and non-gitignored (`!**/*.py` in `.gitignore`),
making it invisible to `git status` warnings but fully in scope for `git clean`.

**Attribution:** Manual/operator git cleanup during migration, not agent action.
Codex, CLC, and OpenCode are not the primary cause. Agent activity during the
subsequent crash-loop period was secondary noise.

**Root cause chain:**
1. File left untracked during freeze/migration (structural vulnerability)
2. `git clean -fdx` run against live canonical repo (deletion event)
3. Both Antigravity launchd plists continued pointing to deleted path (crash-loop)
4. 56-hour crash-loop under KeepAlive=true contributed to Git object store corruption

**Status:** Plists disabled 2026-03-16. Registry created. This ADR updated.

---

## Related

- `ADR-UNRESOLVED-INDEX.md` — Antigravity HQ Runtime Ownership (unresolved, related)
- `tools/ops/git_safety_guard.py` — enforcement scanner
- `tools/run_tool.zsh` — save verb blocked
- `tools/save_now.zsh` — correct artifact persistence path
- Incident: 2026-03-15 Git object store corruption, recovered 2026-03-16
