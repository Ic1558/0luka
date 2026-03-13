# 0LUKA Architecture Contract

## Purpose

This document defines the binding architecture contract for 0LUKA.

It establishes which documents carry architecture authority, how conflicts are
resolved, and which ownership boundaries must remain stable across the
repository.

## Contract Scope

This contract governs:

- layer model
- capability ownership
- runtime ownership
- supervision boundaries
- architecture authority

## Canonical Sources

The canonical architecture sources for this repository are:

- `docs/architecture/0LUKA_LAYER_MODEL.md`
- `docs/architecture/0LUKA_ARCHITECTURE_GUARDRAILS.md`
- `docs/architecture/0LUKA_CAPABILITY_MAP.md`
- `docs/architecture/capabilities/*`
- `docs/architecture/adr/ADR-001-capability-ownership-and-layer-model.md`

Antigravity governance pack (runtime-domain canonical references):

- `docs/architecture/antigravity/ANTIGRAVITY_ARCHITECTURE_CONTRACT.md`
- `docs/architecture/antigravity/ANTIGRAVITY_DRIFT_CLASSIFICATION.md`
- `docs/architecture/antigravity/ANTIGRAVITY_RUNTIME_RECOVERY_RUNBOOK.md`

## Binding Rules

- Architecture law comes from canonical governance documents only.
- Host-specific notes are not architecture law.
- Migration plans are not architecture law.
- Incident documents describe state, not authority.
- Runtime ownership must not be inferred from stale process state.
- Canonical first-hop runtime ownership belongs under `runtime/services/*`.
- PM2 must not directly target app scripts as canonical first-hop runtime
  targets.
- Delegated implementation space may contain runtime-facing code, but delegated
  implementation space is not runtime ownership space.

## Source-of-Truth Priority

The source-of-truth priority order is:

1. Architecture Contract
2. Architecture Decision Records
3. Layer Model
4. Architecture Guardrails
5. Capability documents
6. Incident, migration, and host-specific documents

## Conflict Resolution Rule

If two documents conflict:

- the higher-priority canonical document wins
- the lower-priority document must be updated or marked with an Architecture
  Drift Note

## Architecture Authority Boundaries

Architecture authority must remain separated across these concerns:

- host supervisor authority
  - determines which host-level supervisor manages long-running services
- service entrypoint ownership
  - determines the canonical first-hop runtime entrypoint for a service
- delegated implementation space
  - contains service implementation code without owning runtime supervision law

These boundaries must not be collapsed into a single authority claim.

## ADR References

- `ADR-001: Capability Ownership and Layer Model`
- `ADR-UNRESOLVED: Runtime Service Ownership Model`
- `ADR-UNRESOLVED: Host Supervisor Authority Model`
- `ADR-UNRESOLVED: Antigravity HQ Runtime Ownership`
- `ADR-UNRESOLVED: Legacy Runtime Entrypoint Classification`

Unresolved items are tracked at:
`docs/architecture/adr/ADR-UNRESOLVED-INDEX.md`
