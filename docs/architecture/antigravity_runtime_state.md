# Antigravity Runtime State

## 1. Purpose

This document records the verified Antigravity runtime state observed during
incident investigation.

Its purpose is to describe the current runtime shape, the observed drift
classes, and the canonical runtime ownership model already defined elsewhere in
the workspace architecture.

This document is descriptive, not prescriptive.

## 2. Verified Runtime Observations

- PM2 is currently launching app-local scripts directly from delegated
  implementation space `repos/option`.
- Observed PM2 command targets:
  - `dotenvx run -- ./venv/bin/python3 modules/antigravity/realtime/control_tower.py`
  - `dotenvx run -- ./venv/bin/python3 src/antigravity_prod.py`
- Both configured entrypoints are missing on disk in the current workspace.
- Verified missing paths:
  - `repos/option/modules/antigravity/realtime/control_tower.py`
  - `repos/option/src/antigravity_prod.py`
- Stale bytecode remains for Control Tower:
  - `repos/option/modules/antigravity/realtime/__pycache__/control_tower.cpython-314.pyc`
- No maintained source file for `control_tower.py` or `antigravity_prod.py`
  exists anywhere in the current workspace.
- Settrade SDK environment selector is `prod`.
- Authenticated refresh succeeds, but subsequent market calls still return
  `API-401`.
- `runtime/services/` owns documented first-hop runtime wrappers in the current
  workspace architecture.
- `repos/option/` is delegated implementation space (legacy/delegated), not
  canonical runtime ownership.
- No canonical runtime wrapper currently defined/documented for
  `Antigravity-HQ`; current PM2 process is observed runtime state, not
  ownership authority.

## 3. Runtime Drift Classification

### Runtime Path Drift

Definition

Runtime Path Drift is the condition where runtime supervision targets script
paths that are no longer present in the workspace source tree.

Observed evidence

- PM2 currently points at missing scripts.
- Running processes reference paths that do not exist on disk.
- Historical app-local paths remain visible in runtime state even though they
  are not maintained sources.

### Auth Pairing Drift

Definition

Auth Pairing Drift is the condition where the supervised runtime environment
and the Settrade SDK environment selector do not form a valid authenticated
pairing.

Observed evidence

- Settrade SDK environment selector is `prod`.
- Authenticated refresh succeeds.
- Subsequent market calls still return `API-401`.
- The observed failure pattern is consistent with a pairing mismatch, not
  simple token expiry.

## 4. Canonical Runtime Ownership Model

Canonical runtime ownership for Antigravity is defined under `runtime/services/`
and `runtime/supervisors/`.

Ownership boundary:

- `runtime/services/` owns first-hop runtime wrappers.
- `runtime/supervisors/` owns supervision patterns and always-on process rules.
- `repos/option/` is delegated implementation space (legacy/delegated), not
  canonical runtime ownership.

Under this model, PM2 should target runtime-owned wrappers under
`runtime/services/*` rather than application scripts under `repos/option/`,
`src/`, or `modules/`.

## 5. Canonical Entrypoint Chains

### Antigravity-Monitor

Canonical chain

PM2
-> `runtime/services/antigravity_scan/runner.zsh`
-> delegated implementation

Current workspace state

- wrapper exists
- delegated implementation path is documented as
  `repos/option/src/antigravity_prod.py`
- source file at that documented delegated path is currently missing

### OptionBugHunter

Canonical chain

PM2
-> `runtime/services/antigravity_realtime/runner.zsh`
-> delegated implementation

Current workspace state

- wrapper exists
- delegated implementation path is documented as `repos/option/src/live.js`

### Antigravity-HQ

Canonical chain

Not defined.

Current workspace state

- runtime process exists
- no canonical runtime wrapper currently defined/documented for
  `Antigravity-HQ`; current PM2 process is observed runtime state, not
  ownership authority

## 6. Legacy Runtime Notice

Historical runtime paths may appear in:

- PM2 state
- process tables
- logs

These paths are not authoritative architecture sources in the current
workspace.

Known legacy paths:

- `modules/antigravity/realtime/control_tower.py`
- `src/antigravity_prod.py`

## 7. Architecture Implication

The incident shows that runtime state diverged from repository structure.

The live supervision state still references legacy app-local paths, while the
current workspace architecture defines runtime-owned first-hop supervision under
`runtime/services/`.

## 8. Recovery Model (Architecture-Level)

Architecture-level recovery order:

1. Restore canonical runtime wrapper ownership.
2. Restore maintained delegated implementation.
3. Verify environment pairing.
4. Re-run pre-restart gate proof.

This sequence defines architecture recovery order only. It does not authorize
runtime changes by itself.
