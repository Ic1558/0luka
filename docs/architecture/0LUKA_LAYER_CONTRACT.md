# 0LUKA Layer Contract

## Purpose

This document defines the authoritative path-to-layer mapping for the
repository.

It is the canonical contract used by architecture governance and tooling to
classify repository paths by architectural layer.

## Canonical Layers

Canonical path-to-layer mappings:

- `docs/architecture/` -> architecture governance layer
- `docs/architecture/capabilities/` -> capability governance layer
- `tools/` -> governance/tooling support layer
- `runtime/services/` -> canonical runtime first-hop ownership
- `runtime/supervisors/` -> canonical runtime supervision layer
- `repos/option/` -> delegated implementation space
- `repos/qs/` -> delegated implementation space

## Layer Rules

- Canonical architecture authority lives under `docs/architecture/`.
- Runtime wrappers live under `runtime/services/`.
- Delegated repositories implement behavior but do not define architecture
  authority.
- Runtime supervision and runtime wrappers are distinct ownership layers.
- Tooling may enforce governance but does not redefine architecture law.

## Path Classification Rules

- Unknown path classes must not auto-fail as architecture drift when outside
  the current governance scope.
- Unknown path classes may be reported as unresolved classification for later
  governance decisions.
- Layer mapping enforcement must be derived from this contract rather than host
  runtime state.

## ADR References

- `ADR-001: Capability Ownership and Layer Model`
- `ADR-UNRESOLVED: Runtime Service Ownership Model`
- `ADR-UNRESOLVED: Host Supervisor Authority Model`
- `ADR-UNRESOLVED: Layer Classification Expansion Policy`
