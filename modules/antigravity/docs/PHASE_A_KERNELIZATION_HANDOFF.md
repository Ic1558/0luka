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

## Freeze Rule

Antigravity feature work is frozen during this migration except for:

- bug fixes
- migration support
- runtime stability fixes
- bounded cleanup required for kernelization
