# 0luka Migration Pre-Flight Check & Analysis
**Date:** 2026-01-30
**Status:** 🔴 STOP - Manual Intervention Required Before Migration

## 1. Executive Summary
The proposed migration in `core_brain/ops/governance/migration_map.md` is **insufficient and dangerous**. It accounts for less than 50% of the actual root violations and fails to address hardcoded dependencies in the core kernel. Executing it now would leave the repo in a broken, half-migrated state.

## 2. Critical Blockers

### 🛑 Blocker 1: Hardcoded Core Dependencies
*   **File:** `core/router.py`
*   **Issue:** Contains string literals `"artifacts/tasks/open/"`, `"artifacts/tasks/closed/"`, etc.
*   **Impact:** Moving `artifacts/` to `observability/artifacts/` will cause `Router.propose()` and `Router.audit()` to crash with `FileNotFoundError`.
*   **Fix:** Refactor `router.py` to use a config-driven path or relative path resolution *before* moving directories.

### 🛑 Blocker 2: Incomplete Migration Map
The existing script misses the majority of root clutter.
*   **Missed Directories:** `agents/`, `core_brain/`, `index/`, `interface/`, `mls/`, `plugins/`, `skills/`, `telemetry/`, `tests/`.
*   **Missed Files:** `agents.md`, `test_v1_loop.py`, `IDENTITY.md`, and various session/plan logs.
*   **Ghost Target:** The script tries to move `mcp/`, which does not exist at root.

### 🛑 Blocker 3: The "Brain" Paradox
*   **Issue:** The migration tools themselves live in `core_brain/`, which is a violation.
*   **Risk:** Moving `core_brain/` while running a script *from* `core_brain/` can cause execution errors.

## 3. Comprehensive Violation Audit
(Items not in allowlist: `core`, `ops`, `runtime`, `observability`)

| Item | Type | Current Plan | Recommended Action |
| :--- | :--- | :--- | :--- |
| `g/` | DIR | Delete | **DELETE** (Archive first?) |
| `core_brain/` | DIR | **Missing** | Move contents to `ops/` (governance) or `core/` |
| `artifacts/` | DIR | Move to `observability/` | **Move** (after Router fix) |
| `tools/` | DIR | Move to `ops/` | **Move** |
| `agents/` | DIR | **Missing** | Move to `runtime/agents/` |
| `interface/` | DIR | **Missing** | Move to `runtime/interface/` |
| `skills/` | DIR | **Missing** | Move to `core/catalog/skills` or `runtime/skills` |
| `tests/` | DIR | **Missing** | Move to `ops/tests/` |
| `telemetry/` | DIR | **Missing** | Move to `observability/telemetry/` |
| `workspaces/` | DIR | Move to `runtime/` | **Move** |
| `prps/` | DIR | Merge | Move content to `core/governance/prps/` |

## 4. Revised Migration Strategy

### Step 1: Code Prep (The "Hardening")
1.  Update `core/router.py` to accept `ARTIFACTS_ROOT` from config/env, defaulting to `observability/artifacts`.
2.  Update `core/policy.yaml` if it references absolute paths.

### Step 2: The "Big Move" Script (Draft)
```bash
# Create Destinations
mkdir -p observability/{artifacts,logs,telemetry}
mkdir -p runtime/{agents,interface,workspaces,system}
mkdir -p ops/{tools,tests,governance}
mkdir -p core/catalog

# Move Known Entities
mv artifacts/* observability/artifacts/
mv logs/* observability/logs/
mv telemetry/* observability/telemetry/
mv agents/* runtime/agents/
mv interface/* runtime/interface/
mv workspaces/* runtime/workspaces/
mv system/* runtime/system/
mv tools/* ops/tools/
mv tests/* ops/tests/

# Handle Core Brain (Governance)
# CAREFUL: This moves the script itself if running from here
mv core_brain/ops/governance/* ops/governance/
# ... migrate other brain parts ...

# Cleanup
rm -rf g/
```

## 5. Recommendation
**Do NOT run the existing migration script.**
1.  Authorize the refactoring of `core/router.py`.
2.  Authorize the creation of a comprehensive `ops/maintenance/migrate_root_v2.zsh` script.
3.  Execute v2 script only after Router tests pass.
