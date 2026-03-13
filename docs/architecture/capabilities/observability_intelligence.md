# Capability: Observability Intelligence

## Canonical Owner
observability/

## Layer
Observability Layer

## Runtime Dependencies
Core Layer (schemas / contracts only)

## Description
Observability Intelligence provides the evidence, telemetry, and
interpretation surfaces that allow the 0luka system and its operators
to understand what has happened, why it happened, and how the system
is behaving over time.

This capability owns the collection, storage, and presentation of
runtime evidence, decision history, execution outcomes, and policy
activity metrics. It ensures that system behavior remains transparent,
traceable, and auditable.

Observability Intelligence does not control runtime execution or policy
logic. Its role is to record, surface, and interpret system evidence.

## Responsibilities

- Capture runtime logs and artifacts
- Maintain append-only ledgers for system evidence
- Store decision and execution outcome artifacts
- Provide telemetry and metrics for system behavior
- Surface policy statistics and review signals
- Provide operator-facing reporting and review endpoints
- Maintain audit trails for runtime and policy events
- Support evidence queries for debugging and governance review

## Explicit Non-Ownership

This capability does NOT own:

- Runtime service execution
- Policy definition or policy deployment
- Decision classification or decision persistence logic
- Operator interface control flows
- Domain-specific intelligence algorithms

These responsibilities belong to Runtime Execution,
Policy Governance, Decision Infrastructure,
Operator Control, or domain Module capabilities.

## Allowed Imports

Observability -> Core (contracts / schema only)

## Forbidden Imports

Observability -> Runtime services
Observability -> Interface control logic
Observability -> Module domain intelligence
Observability -> Policy mutation logic

Observability must remain passive and evidence-focused.

## Invariants

- Evidence records must be append-only or atomic snapshots.
- Observability must never mutate runtime or policy state.
- System evidence must remain queryable and auditable.
- Metrics must reflect actual system activity, not derived
  speculation that alters runtime behavior.
- Logs and artifacts must be structured enough for automated review.
- Observability surfaces must remain safe for operator inspection.

## Evidence Model

The system evidence flow follows this structure:

```text
runtime execution
    ->
evidence emission
    ->
observability capture
    ->
append-only ledger / artifact storage
    ->
review surfaces / metrics
    ->
operator insight

Observability does not alter system state in this process.
```

## Typical Implementations

Examples within the repository:
- observability/logs/
- observability/artifacts/
- observability/reports/
- observability/ledgers/
- policy metrics endpoints
- decision history reporting
- runtime telemetry summaries

## Relationship to Runtime Execution

Runtime emits evidence into observability surfaces.

Runtime may write logs, artifacts, or metrics through approved
append-only interfaces, but runtime does not control observability
storage policies or retention governance.

## Relationship to Decision Infrastructure

Decision Infrastructure records authoritative decision state.

Observability Intelligence provides reporting, metrics, and review
surfaces for those decisions but does not control the decision ledger.

## Relationship to Policy Governance

Policy Governance may consume observability signals during policy
review or simulation, but observability does not participate in
policy evaluation or policy mutation.

## Relationship to Operator Control

Operator interfaces may display observability data for inspection,
debugging, and review.

Observability Intelligence provides the evidence surfaces that make
those operator views possible, but it does not implement UI logic.
