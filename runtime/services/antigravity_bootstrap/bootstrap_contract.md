# Antigravity Bootstrap Contract

This file defines the canonical 0luka-owned startup contract for Antigravity
runtime services.

Authority:

- secrets law: `core/governance/secrets_policy.md`
- supervision owner: `runtime/supervisors/ANTIGRAVITY_RUNTIME_OWNERSHIP.md`
- bootstrap owner: `runtime/services/antigravity_bootstrap/pm2_start.zsh`

## Startup Convention

First-hop ownership must be:

1. `runtime/services/antigravity_bootstrap/pm2_start.zsh`
2. `runtime/services/antigravity_scan/runner.zsh`
3. `runtime/services/antigravity_realtime/runner.zsh`
4. delegated implementation under `repos/option/src/`

## Approved Secret Injection Boundary

- `dotenvx run -- ...`

Antigravity runtime wrappers may use `dotenvx` to inject secrets at startup,
but that rule is owned by 0luka governance and runtime, not by Antigravity.

## Operational Expectations

- bootstrap wrappers may reference variable names only
- wrappers must not print or persist secret values
- PM2/bootstrap paths point first to 0luka runtime-owned wrappers
- repo-local bootstrap scripts are discoverable legacy paths only

## Deferred

- full removal of legacy repo-local bootstrap scripts
- deeper implementation relocation out of `repos/option/src/`
- any change to trading or strategy logic
