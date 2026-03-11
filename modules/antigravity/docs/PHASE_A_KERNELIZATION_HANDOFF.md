# Antigravity Kernelization Handoff (Phase A)

## What Moved Into 0luka Ownership

### Core Governance

- secrets discipline is now explicitly owned by:
  - `core/governance/secrets_policy.md`

### Runtime

- process persistence / supervisor ownership is now explicitly anchored at:
  - `runtime/supervisors/ANTIGRAVITY_RUNTIME_OWNERSHIP.md`
  - `runtime/services/README.md`

### Observability

- Antigravity runtime log ownership is now explicitly anchored at:
  - `observability/logs/antigravity/README.md`

## What Remains In Antigravity Module Space

- domain intelligence
- realtime detection logic
- connectors
- bounded module docs

Target module skeleton:

- `modules/antigravity/intelligence/`
- `modules/antigravity/realtime/`
- `modules/antigravity/connectors/`
- `modules/antigravity/infra/`
- `modules/antigravity/docs/`

## Discoverable Existing Entrypoints Preserved

- `repos/option/tools/deploy_prod.sh`
- `repos/option/src/antigravity_prod.py`
- `repos/option/src/live.js`
- `system/antigravity/scripts/dispatch_latest.zsh`

Phase A preserves these entrypoints and does not break runtime discoverability.

## Intentionally Deferred

- large code relocation out of `repos/option/`
- broad PM2/service rewrite
- full log-path rewiring for every Antigravity script
- Antigravity feature growth
- domain decision logic changes

## Phase A.1 Runtime Entrypoint Relocation

Phase A.1 introduces 0luka-owned runtime wrappers so service startup no longer
points first at app-local source files.

Old -> new first-hop ownership mapping:

- `repos/option/src/antigravity_prod.py`
  -> `runtime/services/antigravity_scan/runner.zsh`
- `repos/option/src/live.js`
  -> `runtime/services/antigravity_realtime/runner.zsh`

The delegated implementation remains in `repos/option/src/` for now. Runtime
ownership moves first; full code relocation is deferred.

Bootstrap normalization added in Phase A.1:

- legacy discoverable script remains:
  - `repos/option/tools/deploy_prod.sh`
- runtime-owned bootstrap path now exists:
  - `runtime/services/antigravity_bootstrap/pm2_start.zsh`

## Phase A.2 Log / State Path Normalization

Old -> new ownership mapping:

- `repos/option/logs/antigravity.log`
  -> `observability/logs/antigravity/antigravity.log`
- PM2 stdout/stderr for `Antigravity-Monitor`
  -> `observability/logs/antigravity/antigravity_monitor.out.log`
  -> `observability/logs/antigravity/antigravity_monitor.err.log`
- PM2 stdout/stderr for `OptionBugHunter`
  -> `observability/logs/antigravity/option_bug_hunter.out.log`
  -> `observability/logs/antigravity/option_bug_hunter.err.log`
- startup/runtime wrapper state
  -> `runtime/state/antigravity/bootstrap_state.json`
  -> `runtime/state/antigravity/antigravity_scan_runtime.json`
  -> `runtime/state/antigravity/antigravity_realtime_runtime.json`

Legacy repo-local log paths may still exist as transitional compatibility adapters,
but they are no longer the primary operational truth.

Phase A.2 does not relocate domain code or redesign trading behavior. It only
normalizes runtime evidence and current-state ownership toward 0luka.

## Freeze Rule

Antigravity feature work is frozen during this migration except for:

- bug fixes
- migration support
- runtime stability fixes
- bounded cleanup required for kernelization
