# Capability: Operator Control Surface

## Canonical Owner
interface/operator/

## Layer
Interface Layer

## Runtime Dependencies
System / Services Layer
Core Layer (read-only)
Observability Layer (read-only)

## Description
The Operator Control Surface provides the human interaction boundary for the 0luka system.
It allows operators to inspect system state, review decisions, approve or reject actions,
initiate controlled retries, and review policy simulations and proposals.

This capability is responsible only for human interaction and visibility, not for
runtime execution or policy mutation.

## Responsibilities
- Display decision state and history
- Provide approval and rejection controls
- Allow bounded retry or escalation requests
- Present policy review and tuning simulation results
- Surface runtime observability and artifacts
- Allow proposal authoring and inspection

## Explicit Non-Ownership
This capability does NOT own:

- Runtime services
- Policy execution
- Decision persistence
- Execution bridge logic
- Policy mutation
- Ledger storage
- System supervision

Those responsibilities belong to the Core Layer, System/Services Layer,
or Observability Layer.

## Allowed Imports
Interface -> System / Services
Interface -> Core (read-only contracts)
Interface -> Observability (read-only)

## Forbidden Imports
Interface -> Runtime supervisors
Interface -> Module execution logic
Interface -> Direct state mutation in ledgers

## Invariants
- Operator interaction must not bypass policy governance.
- All actions initiated through the interface must pass through
  the system control plane.
- The interface must remain optional: the system must continue
  functioning even if the operator UI is offline.

## Typical Implementations
Examples within the repository:

- interface/operator/mission_control_server.py
- Mission Control UI
- Operator dashboards and control panels
