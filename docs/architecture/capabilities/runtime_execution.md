# Capability: Runtime Execution

## Canonical Owner
runtime/

## Layer
Runtime Layer

## Runtime Dependencies
Core Layer
Observability Layer (append-only / read-only evidence surfaces)

## Description
Runtime Execution owns the always-on execution behavior of the 0luka system.

It is responsible for taking governed decisions and policy-constrained inputs
and turning them into supervised runtime actions. This includes long-running
services, execution bridges, bounded retries, reconciliation of outcomes,
service supervision, and runtime health discipline.

Runtime Execution is the layer where governed intent becomes real system
activity, but it must always remain subordinate to Core policy and decision
authority.

## Responsibilities

- Run always-on services
- Own service lifecycle and restart discipline
- Execute approved runtime actions through bounded execution paths
- Perform controlled retry and re-escalation when explicitly allowed
- Reconcile execution outcomes back into system state
- Maintain runtime health checks and heartbeat discipline
- Manage runtime supervision and service ownership
- Expose runtime state to observability and operator surfaces
- Ensure runtime behavior obeys active policy and decision constraints

## Explicit Non-Ownership

This capability does NOT own:

- Policy definition or policy lifecycle
- Decision classification or decision persistence
- Operator approval / rejection logic
- Domain-specific trading intelligence
- Observability ledgers or artifact storage

These responsibilities belong to Policy Governance,
Decision Infrastructure, Operator Control, domain Modules,
or Observability capabilities.

## Allowed Imports

Runtime -> Core
Runtime -> Observability
Runtime -> Module capability packs (bounded domain logic only)

## Forbidden Imports

Runtime -> Interface
Runtime -> Operator UI surfaces
Runtime -> Capability ownership docs or report logic
Runtime -> Direct policy mutation logic

Runtime must not depend on the Interface Layer for survival,
and it must not redefine policy or decision authority.

## Invariants

- Runtime may execute only through governed paths.
- Runtime must treat policy as authoritative input.
- Runtime must never mutate live policy directly.
- Runtime must never silently alter decision history.
- Retry behavior must remain bounded and explicitly governed.
- Execution outcomes must reconcile back into authoritative state.
- Runtime supervision must be deterministic and auditable.
- The system must continue functioning if operator UI is offline.

## Execution Model

The runtime execution flow follows this pattern:

```text
system event
    ->
decision infrastructure
    ->
policy governance
    ->
runtime execution path
    ->
execution outcome
    ->
reconciliation
    ->
observability / operator surface

No runtime path may bypass decision or policy authority.
```

## Typical Implementations

Examples within the repository:
- runtime/services/
- runtime/supervisors/
- execution bridge implementations
- retry / reconciliation paths
- health and heartbeat services
- long-running service entrypoints

## Relationship to Decision Infrastructure

Runtime Execution does not classify or resolve decisions.

It may consume approved or governed decisions and perform execution,
but all decision authority remains outside the runtime layer.

Runtime outcomes must be reported back into the decision system as
recorded results.

## Relationship to Policy Governance

Runtime Execution is subordinate to Policy Governance.

Policy defines what is allowed, frozen, reviewable, or deployable.
Runtime may consume active policy state, but it may not alter policy
state directly.

## Relationship to Modules

Runtime may invoke bounded module logic when domain-specific behavior
is required.

However, modules must remain capability packs and must not take over
runtime supervision, service ownership, or policy authority.

## Relationship to Observability

Runtime emits evidence.

Logs, artifacts, ledgers, metrics, and reports belong to Observability.
Runtime may write to these surfaces through approved append-only or
atomic interfaces, but it does not own observability storage policy.
