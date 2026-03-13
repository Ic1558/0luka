# Capability: Agent Execution

## Canonical Owner
agents/

## Layer
System / Services Layer

## Runtime Dependencies
Core Layer
Runtime Layer
Observability Layer (append-only evidence)

## Description
Agent Execution governs the behavior of system agents that perform
bounded autonomous or semi-autonomous tasks within the 0luka system.

Agents may assist runtime services, analyze system evidence, generate
suggestions, or perform domain-specific tasks, but they must operate
under strict policy governance and execution constraints.

Agents do not control the system. They operate as bounded capability
workers that execute tasks within the limits defined by policy,
decision infrastructure, and runtime supervision.

## Responsibilities

- Execute bounded agent tasks
- Perform analysis or assistance tasks under runtime supervision
- Generate suggestions or recommendations
- Consume system evidence and telemetry
- Operate within governed execution boundaries
- Record actions and outputs as observable evidence
- Respect system policy constraints and freeze states
- Remain restartable and supervised by runtime services

## Explicit Non-Ownership

This capability does NOT own:

- Policy definition or lifecycle
- Decision persistence or classification
- Runtime service supervision
- System governance rules
- Observability storage policy
- Operator interface control

These responsibilities belong to Policy Governance,
Decision Infrastructure, Runtime Execution,
Observability Intelligence, or Operator Control.

## Allowed Imports

Agents -> Core (contracts / policies)
Agents -> Runtime services
Agents -> Observability (read-only evidence)
Agents -> Modules (domain intelligence)

## Forbidden Imports

Agents -> Interface Layer
Agents -> Policy mutation logic
Agents -> Runtime supervisors
Agents -> Decision ledger mutation

Agents must remain subordinate to runtime supervision
and policy governance.

## Invariants

- Agents must operate within bounded execution paths.
- Agents must not mutate policy state.
- Agents must not bypass decision infrastructure.
- Agent outputs must be observable and auditable.
- Agent execution must remain restartable and supervised.
- Agents must never become the system authority.

## Execution Model

Agent execution follows a supervised pattern:

```text
system event
    ->
runtime supervision
    ->
agent invocation
    ->
analysis / task execution
    ->
result emitted
    ->
observability record

Agents may assist runtime behavior but may not control
system governance.
```

## Typical Implementations

Examples within the repository:
- agents/
- system assistants
- helper analysis workers
- suggestion engines
- task automation agents
