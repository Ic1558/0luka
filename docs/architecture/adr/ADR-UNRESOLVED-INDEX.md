# ADR Unresolved Index

## Purpose

This document records architecture decisions that are known, tracked,
and intentionally not yet resolved.

Each item in this index represents a governance gap that has been
identified through architecture review, tooling signals, or invariant
analysis. Items are tracked here so they are not silently ignored and
not silently implemented as if already decided.

This document is a tracking artifact only. It does not carry
architecture authority.

---

## Status

All items below are: **UNRESOLVED — tracked, not ignored**

---

## Tracked Unresolved Decisions

---

### ADR-UNRESOLVED: Host Supervisor Authority Model

**Current status:**
Tracked by architecture_guard as a non-failing unresolved signal.
The Architecture Contract (see: Architecture Authority Boundaries)
acknowledges host supervisor authority as a distinct concern but does
not resolve which host-level supervisor holds canonical authority for
which service classes on which machines.

**Why unresolved:**
The migration from PM2 direct execution to launchd-supervised wrappers
under runtime/services/ is ongoing. Formalizing the authority model
requires the supervisor migration to reach a stable state before the
model can be declared canonical. Premature resolution risks locking in
a rule that contradicts in-progress migration work.

**Affected docs:**
- docs/architecture/0LUKA_ARCHITECTURE_CONTRACT.md
- docs/architecture/mac-mini-migration-plan.md
- docs/architecture/mac-mini-supervisor-decision.md
- docs/architecture/0LUKA_ARCHITECTURE_INVARIANTS.md

**Blocking impact:**
Non-blocking to current architecture_guard PASS.
Does not block PR merges or current governance enforcement.
Blocks future host-specific supervisor audit rules from being added
to architecture_guard without risk of premature enforcement.

**Non-goals:**
This unresolved item does not choose a supervisor.
It does not initiate migration steps.
It does not define launchd vs PM2 authority.
It does not modify any runtime, plist, or PM2 configuration.

---

### ADR-UNRESOLVED: Antigravity HQ Runtime Ownership

**Current status:**
Tracked by architecture_guard as a non-failing unresolved signal.
The Antigravity-HQ PM2 process runs from delegated implementation
space (repos/option/ or modules/). No canonical runtime wrapper under
runtime/services/ exists for the Antigravity HQ service.
Architecture Invariant #7 classifies PM2 direct execution of app
scripts as non-canonical.

**Why unresolved:**
Adding a canonical runtime/services/ wrapper requires a governance
decision about whether the service should be promoted to canonical
supervised ownership or maintained as a delegated entrypoint with
explicit classification. That decision depends in part on Host
Supervisor Authority Model (above) being resolved first.

**Affected docs:**
- docs/architecture/0LUKA_ARCHITECTURE_CONTRACT.md
- docs/architecture/0LUKA_ARCHITECTURE_INVARIANTS.md
- docs/architecture/mac-mini-runtime-inventory.md
- docs/architecture/capabilities/antigravity_module.md
- docs/architecture/capabilities/runtime_execution.md

**Blocking impact:**
Non-blocking to current architecture_guard PASS.
Does not block PR merges.
Blocks the system from having a complete canonical runtime ownership
map for Antigravity services.

**Non-goals:**
Does not resolve whether to create a runtime/services/ wrapper.
Does not touch PM2 configuration.
Does not touch launchd plists.
Does not modify repos/option/ or modules/.

---

### ADR-UNRESOLVED: Legacy Runtime Entrypoint Classification

**Current status:**
Architecture Invariant #8 states: "Missing entrypoint paths
referenced by live runtime imply architecture drift."
PM2 currently references paths in delegated implementation space
(modules/antigravity/realtime/, repos/option/). These have been
formally classified as delegated entrypoints (PR #317) rather than
canonical runtime entrypoints, but the general rule for classifying
"legacy entrypoints" vs "delegated entrypoints" vs "canonical
entrypoints" has not been formalized as a resolved ADR.

**Why unresolved:**
The Layer Contract classifies runtime/services/ as canonical first-hop
ownership. The formal rule for how a path is classified as
"delegated," "legacy," or "migrated" — and what governance action
each classification triggers — has not been decided. Resolving this
requires the layer classification expansion policy to be decided first.

**Affected docs:**
- docs/architecture/0LUKA_LAYER_CONTRACT.md
- docs/architecture/0LUKA_ARCHITECTURE_INVARIANTS.md
- docs/architecture/antigravity_runtime_state.md
- docs/architecture/mac-mini-runtime-inventory.md

**Blocking impact:**
Non-blocking to current architecture_guard PASS.
Does not block PR merges.
Blocks precision on which path classes trigger a drift failure vs
an unresolved signal vs a clean pass in architecture_guard.

**Non-goals:**
Does not reclassify any existing paths.
Does not modify PM2 targets.
Does not create runtime/services/ wrappers.
Does not alter architecture_guard logic.

---

### ADR-UNRESOLVED: Runtime Service Ownership Model

**Current status:**
The Architecture Contract and Invariants establish that canonical
runtime first-hop ownership belongs under runtime/services/. However,
the formal model defining how services transition from delegated
implementation space to canonical runtime ownership — including what
governance steps are required and what constitutes a valid transition
— has not been resolved as an ADR.

**Why unresolved:**
A complete ownership model requires alignment between:
- capability ownership (capabilities/*.md)
- host supervisor authority (unresolved — see above)
- layer contract path classification (partially unresolved)
- migration policy for delegated entrypoints

Until the other unresolved decisions reach a stable state, a complete
runtime service ownership model cannot be finalized without
prematurely locking in rules that may conflict with emerging practice.

**Affected docs:**
- docs/architecture/0LUKA_ARCHITECTURE_CONTRACT.md
- docs/architecture/0LUKA_ARCHITECTURE_INVARIANTS.md
- docs/architecture/0LUKA_LAYER_CONTRACT.md
- docs/architecture/capabilities/runtime_execution.md

**Blocking impact:**
Non-blocking to current architecture_guard PASS.
Does not block PR merges.
Blocks future architecture tooling that would verify full
ownership-to-service alignment across the repository.

**Non-goals:**
Does not define the ownership model.
Does not create runtime/services/ entries.
Does not modify capability documents.

---

## Rules

- **Unresolved means tracked, not ignored.**
  Each item above is actively maintained in this index until a
  formal ADR is created to resolve it.

- **Unresolved items are not architecture authority.**
  Code or docs must not implement behavior on the assumption that
  an unresolved item has been decided in any particular direction.

- **Unresolved items must not be silently resolved.**
  Any PR that implements behavior that presupposes an answer to an
  unresolved item must first create a formal ADR to resolve it.

- **Future PRs may reference this index.**
  Until a formal ADR exists, reference this file as the tracking
  source for the relevant governance gap.

---

## Relationship to architecture_guard

architecture_guard (tools/architecture_guard.sh) tracks unresolved
rules as non-failing signals. These signals are reported in the guard
output under "Unresolved rules" but do not cause the guard to exit
with a failure code.

The guard currently hardcodes two unresolved rules:
- Host Supervisor Authority Model
- Antigravity HQ Runtime Ownership

It also scans docs/architecture/0LUKA_ARCHITECTURE_CONTRACT.md and
docs/architecture/0LUKA_ARCHITECTURE_INVARIANTS.md for any additional
ADR-UNRESOLVED references and appends them to the unresolved signal
list.

This index documents all four current unresolved signals in a single
discoverable location. The guard result remains PASS as long as these
items remain in unresolved status and no canonical governance
documents contradict the architectural invariants.

---

## Document Status

Status: Active tracking artifact

Changes to this document require an architecture PR.

To resolve an item: create a formal ADR in docs/architecture/adr/,
link it here, and remove the entry from the Tracked Unresolved
Decisions section.
