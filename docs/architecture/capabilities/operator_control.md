# Operator Control Capability

## Layer

Interface Layer

## Purpose

Provide human operator visibility and manual control surfaces without autonomous execution.

## Scope

- Mission Control UI and operator dashboards
- Read-only system status and decision previews
- Explicit operator-initiated actions (if and when allowed)

## Non-Goals

- Autonomous remediation or policy execution
- Hidden side effects
- Direct mutation of runtime state without governance

## Interfaces

- Inputs: observability artifacts, decision previews, policy constraints
- Outputs: operator-visible state, acknowledgements, manual commands (explicit)

## Ownership

- Canonical owner: this document
- Execution owner: operator surfaces in the interface layer
- Change authority: docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md
