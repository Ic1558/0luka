# Antigravity Runtime Supervision Ownership

## Purpose

This document moves Antigravity process persistence and runtime supervision
ownership under 0luka runtime.

Antigravity may remain a bounded module/cockpit, but it must not remain the
host of system survival.

## Ownership Boundary

- `runtime/supervisors/` owns supervisor patterns and always-on process rules.
- `runtime/services/` is the bounded home for service definitions and startup
  conventions.
- `repos/option/` contains Antigravity domain code and bounded startup scripts,
  but no longer owns the survival-layer contract.

## Current Discoverable Entrypoints

- `repos/option/tools/deploy_prod.sh`
- `repos/option/src/antigravity_prod.py`
- `repos/option/src/live.js`
- `system/antigravity/scripts/dispatch_latest.zsh`

These remain discoverable in Phase A and are not removed in this migration pass.

## Phase A.1 Runtime Wrapper Mapping

0luka runtime now owns the first-hop service entrypoints:

- `runtime/services/antigravity_scan/runner.zsh`
  - delegates to `repos/option/src/antigravity_prod.py`
- `runtime/services/antigravity_realtime/runner.zsh`
  - delegates to `repos/option/src/live.js`

Supervisor/bootstrap ownership should target the runtime wrapper first, then
delegate into the legacy implementation.

Current PM2 mapping:

- `Antigravity-Monitor` -> `runtime/services/antigravity_scan/runner.zsh`
- `OptionBugHunter` -> `runtime/services/antigravity_realtime/runner.zsh`
- runtime bootstrap owner:
  - `runtime/services/antigravity_bootstrap/pm2_start.zsh`

## Phase A.2 Log / State Ownership Mapping

Canonical log ownership:

- `observability/logs/antigravity/antigravity.log`
- `observability/logs/antigravity/antigravity_monitor.out.log`
- `observability/logs/antigravity/antigravity_monitor.err.log`
- `observability/logs/antigravity/option_bug_hunter.out.log`
- `observability/logs/antigravity/option_bug_hunter.err.log`

Canonical runtime state ownership:

- `runtime/state/antigravity/bootstrap_state.json`
- `runtime/state/antigravity/antigravity_scan_runtime.json`
- `runtime/state/antigravity/antigravity_realtime_runtime.json`

Legacy app-local `repos/option/logs/` remains a compatibility path only. The
runtime wrappers normalize it toward the canonical 0luka-owned observability
path.

## Runtime Standard

1. PM2/startup behavior is governed by 0luka runtime policy.
2. Secrets injection for supervised processes must follow
   `core/governance/secrets_policy.md`.
3. Supervisor ownership must stay outside Antigravity feature code.
4. Runtime persistence must be auditable through 0luka observability paths.

## Phase A Freeze

Allowed:

- runtime stability fixes
- migration support
- bounded path cleanup

Disallowed:

- new Antigravity scanners
- new strategy services
- new feature daemons
- new deploy flows outside kernelization work

## Deferred

Phase A does not rewrite all Antigravity startup scripts into final kernel form.
It establishes ownership and migration anchors only.

Phase A.1 still defers:

- relocating Python/Node implementation code out of `repos/option/src/`
- broad PM2 topology redesign
- full observability path rewiring for every Antigravity process
