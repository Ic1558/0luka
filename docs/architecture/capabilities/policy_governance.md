# Capability: Policy Governance

## Canonical Owner
core/policy/

## Layer
Core Layer

## Runtime Dependencies
Observability Layer (read-only)

## Description
Policy Governance defines the authoritative rules and lifecycle governing
system behavior in 0luka. It manages how policies are proposed, reviewed,
approved, deployed, rolled back, and observed.

This capability ensures that system behavior evolves only through
explicit, auditable governance rather than uncontrolled runtime mutation.

Policy Governance acts as the highest authority capability in the
system's control hierarchy.

## Responsibilities

- Define policy rules and evaluation logic
- Maintain policy version history
- Manage proposal lifecycle (propose -> review -> approve/reject)
- Control policy deployment
- Provide rollback capability for deployed policies
- Maintain append-only policy change ledger
- Enforce freeze/unfreeze safety gates
- Expose active policy state to runtime services
- Provide policy observability metrics and review surfaces

## Explicit Non-Ownership

This capability does NOT own:

- Runtime service execution
- Operator interface rendering
- Decision persistence infrastructure
- Agent behavior implementation
- Observability storage systems

These belong to the System / Services Layer, Interface Layer,
Decision Infrastructure capability, or Observability capability.

## Allowed Imports

Core -> Observability (contracts / schema only)

## Forbidden Imports

Core -> Interface
Core -> Runtime service implementations
Core -> Module domain logic

Policy governance must remain independent from runtime and UI layers
to preserve deterministic system behavior.

## Invariants

- Policies must never mutate themselves automatically.
- All policy changes must pass through the proposal lifecycle.
- Live policy state must be versioned and queryable.
- Deployment of a policy must be explicitly approved.
- Rollback must be explicit and auditable.
- Simulation and tuning must never mutate live policy.
- Runtime services may read policy but must not modify it.

## Policy Lifecycle Model

The policy lifecycle follows a strict governance flow:

proposal
|
review
|
approve / reject
|
deploy
|
active policy version
|
rollback (optional)

No step in this lifecycle may be skipped.

## Typical Implementations

Examples within the repository:

- core/policy/policy_engine.py
- core/policy/policy_versions.py
- core/policy/policy_proposals.py
- policy deployment and rollback surfaces
- policy review and simulation endpoints

## Relationship to Runtime

Runtime services may query the active policy state but may not
directly alter it.

Runtime behavior must treat policy as authoritative input, not
as a mutable configuration surface.
