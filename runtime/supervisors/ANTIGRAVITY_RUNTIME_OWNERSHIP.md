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
