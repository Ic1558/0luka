# PLAN — Baseline Health Tracked

## Goal
Make `origin/main` reproducibly green in a clean worktree/clone without relying on untracked local artifacts.

## Scope
- Add missing tracked schema files under `interface/schemas/` required by verification suite.
- Keep smoke canary deterministic under temp `ROOT` during pytest suite order.
- Make Phase1D trusted-uri test deterministic by setting/restoring `0LUKA_ROOT` explicitly.

## Non-Goals
- No Phase 15.3 changes.
- No ops/tooling refactor.
- No policy relaxation.
