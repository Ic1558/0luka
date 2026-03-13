# Capability: Decision Infrastructure

## Canonical Owner
core/decision/

## Layer
Core Layer

## Runtime Dependencies
Observability Layer (read-only)

## Description
Decision Infrastructure provides the deterministic mechanism through which
the 0luka system records, evaluates, and resolves decisions about runtime
events.

It acts as the control bridge between system observations and governed
actions. Decisions capture system interpretation of events and allow
operator-supervised resolution before actions are executed.

The decision layer ensures that runtime behavior is traceable, auditable,
and reviewable through append-only evidence and deterministic state
transitions.

## Responsibilities

- Persist decision records
- Maintain append-only decision history
- Maintain the current decision state ("latest decision")
- Provide deterministic decision classification
- Support operator approval and rejection
- Record resolution outcomes
- Expose decision data to operator control surfaces
- Provide decision history for observability and audits

## Explicit Non-Ownership

This capability does NOT own:

- Runtime service execution
- Policy rule evaluation
- Agent logic or domain algorithms
- Operator interface rendering
- Observability storage systems

These responsibilities belong to Runtime Execution,
Policy Governance, Interface Layer, or Observability capabilities.

## Allowed Imports

Core -> Observability (contracts / schema only)

## Forbidden Imports

Core -> Interface
Core -> Runtime service implementations
Core -> Module domain logic

Decision logic must remain deterministic and independent of
runtime behavior and UI surfaces.

## Invariants

- Decision state transitions must be deterministic.
- Decision history must be append-only.
- A decision must have a clearly defined resolution state.
- Runtime actions must not occur without a valid decision path.
- Decision persistence must be independent of runtime services.
- Operator actions must be recorded as part of decision history.

## Decision Lifecycle Model

The decision lifecycle follows a structured flow:

event
|
classification
|
decision record created
|
operator review (optional)
|
approve / reject / retry / escalate
|
resolution recorded

No decision state may be silently altered or deleted.

## Typical Implementations

Examples within the repository:

- core/decision/decision_engine.py
- core/decision/decision_ledger.py
- core/decision/decision_state.py
- decision persistence helpers
- decision review surfaces
- decision history endpoints

## Relationship to Policy Governance

Decision Infrastructure operates under Policy Governance.

Policies may influence how decisions are classified or routed,
but decisions themselves remain independent records that
capture system interpretation and operator resolution.

## Relationship to Runtime

Runtime services may act upon approved decisions but may not
mutate decision state directly.

All runtime outcomes must reconcile back into the decision
infrastructure as recorded results.
