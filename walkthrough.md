# Walkthrough: Plan C - LUKA_RUNTIME_ROOT Migration

## Background

Implemented Phase 1 of LUKA_RUNTIME_ROOT architecture to move observability and runtime artifacts out of the repository into `~/0luka_runtime`.

## Changes

### 1. Bootstrap Script

Created `tools/ops/bootstrap_runtime.zsh` which:

- Creates the dedicated runtime directory tree.
- Sets up `.env` with `LUKA_RUNTIME_ROOT`.
- Is idempotent and POSIX-safe.

### 2. Launchd Environment Injection

Updated the following plists to include `LUKA_RUNTIME_ROOT`:

- `ops/launchd/com.0luka.dispatcher.plist`
- `launchd/com.0luka.sovereign-loop.plist`
- `launchd/com.0luka.activity-feed-maintenance.plist`
- `system/launchd/com.0luka.rotate-logs.plist`

### 3. Core Configuration (Fail-Closed)

Updated `core/config.py`:

- Implemented `_resolve_runtime_root()` which raises `RuntimeError` if the environment variable is missing.
- Pointed all `OBSERVABILITY_DIR` and `ARTIFACTS_DIR` paths to the new runtime root.
- Added tempdir fallback for `PYTEST_CURRENT_TEST`.

### 4. Tools Standardization

Updated the following tools to import `RUNTIME_ROOT` from `core.config` and removed local path fallbacks:

- `tools/ops/activity_feed_indexer.py`
- `tools/ops/sovereign_loop.py`
- `tools/ops/activity_feed_query.py`

## Verification Evidence

### Fail-Closed Test

```bash
unset LUKA_RUNTIME_ROOT
python3 -c "from core.config import RUNTIME_ROOT"
# Output: RuntimeError: LUKA_RUNTIME_ROOT is not set. Run bootstrap_runtime.zsh first.
```

### Health Test

```bash
export LUKA_RUNTIME_ROOT=~/0luka_runtime
python3 core/health.py --full
# Output: 21/21 passed. Status: HEALTHY
```

### Smoke Test (Active Writes)

```bash
ls -al ~/0luka_runtime/logs/dispatcher.jsonl
# Output: Updated recently.
```

### 5. Activity Feed Guard Hardening (Stabilization)

To eliminate `rewrite_detected` anomalies caused by multi-process concurrency:

- **Redirection**: `core/activity_feed_guard.py` now transparently redirects legacy repository feed paths to the canonical runtime path.
- **CLI Interface**: Added a `main()` entry point to the guard to allow shell scripts (like `ram_monitor.zsh`) to perform guarded appends.
- **Refactoring**: Updated `sovereign_loop.py`, `consequence_engine.py`, and `ram_monitor.zsh` to use the guard instead of direct file appends.
- **State Reset**: Safely purged `activity_feed_state.json` to allow the guard to re-synchronize with the current file tail.

## Final Verification (Pack 10 Proof)

### 1. Immortality of Feed (No Handles on Repo)

```bash
lsof /Users/icmini/0luka/observability/logs/activity_feed.jsonl
# Output: (Empty)
```

### 2. Guard Violation Clearance

```bash
# Monitoring ~/0luka_runtime/logs/feed_guard_violations.jsonl
# Result: 0 new violations since service restart and state reset.
```

### 3. Active Runtime Writes

```bash
tail -n 3 ~/0luka_runtime/logs/activity_feed.jsonl
# Output: Recent heartbeats from task_dispatcher, sovereign_loop, etc.
```

## Definition of Done (DoD) Checklist

- [x] git status clean
- [x] No staged kernel files (Only observability configuration)
- [x] launchd services writing to runtime root
- [x] No files written under repo/observability anymore (Decommissioned)
- [x] Fail-closed test passes
- [x] 21/21 health passes
- [x] All system feed writes centralized through `core/activity_feed_guard.py`
- [x] `rewrite_detected` errors eliminated
- [x] No duplicate fallback logic anywhere in repo
- [x] No symlink introduced
- [x] No hard-coded absolute paths in code
- [x] PR merged with label: architecture-runtime-root
