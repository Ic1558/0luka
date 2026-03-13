# 0LUKA Architecture Invariants

## Purpose

This document defines the small set of invariant rules that must remain true as
the repository evolves.

These invariants are architecture law. They are intended to be checked by
architecture review and repository tooling.

## Invariants

1. Core does not depend on higher layers.
2. Runtime supervision does not define policy authority.
3. Capability ownership has exactly one canonical owner.
4. Host runtime state is not architecture truth.
5. Canonical runtime first-hop ownership belongs under `runtime/services/*`.
6. Delegated implementation space is not runtime ownership space.
7. PM2 direct execution of app-local scripts is non-canonical.
8. Missing entrypoint paths referenced by live runtime imply architecture drift.
9. Incident documents may describe failure state but do not redefine
   architecture.
10. Architecture claims must be anchored to canonical governance documents or
    ADRs.
11. Canonical architecture ownership must be defined by `docs/architecture/*`.
12. Canonical runtime first-hop ownership must be defined under
    `runtime/services/*`.
13. Delegated implementation spaces must not be treated as runtime ownership
    layers.
14. Runtime supervision and runtime ownership are distinct concepts.
15. Path-to-layer classification must be derived from the layer contract, not
    host runtime state.

## Invariant Violation Examples

Examples from the current repository context:

- PM2 targeting `modules/antigravity/realtime/control_tower.py` while that path
  is missing on disk.
- PM2 targeting `src/antigravity_prod.py` while that path is missing on disk.
- Host-specific inventory documents describing `Antigravity-HQ` as canonical
  runtime ownership while canonical runtime wrapper ownership is not defined for
  that service.

## Drift Signals

Architecture drift signals include:

- conflicting ownership language across documents
- stale path references treated as maintained sources
- canonical-vs-host-document contradictions
- undocumented supervisor authority claims

## Enforcement Intent

These invariants are intended to be enforced through architecture tooling,
documentation review, and governance PR discipline.

## ADR References

- `ADR-001: Capability Ownership and Layer Model`
- `ADR-UNRESOLVED: Runtime Service Ownership Model`
- `ADR-UNRESOLVED: Host Supervisor Authority Model`
- `ADR-UNRESOLVED: Antigravity HQ Runtime Ownership`
- `ADR-UNRESOLVED: Legacy Runtime Entrypoint Classification`
