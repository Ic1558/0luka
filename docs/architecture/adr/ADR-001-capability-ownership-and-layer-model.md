# ADR-001: Capability Ownership and Layer Model

## Status

Accepted

## Date

2026-03-13

## Context

The 0luka repository has grown into a multi-layer system containing:

- core governance and policy logic
- runtime services
- observability systems
- operator interfaces
- domain modules
- agent execution paths

Without an explicit layer model and capability ownership system, the repo risks:

- architecture entanglement
- cross-layer drift
- runtime fragility
- duplicate ownership
- agent chaos

To prevent this, the architecture must define:

1. canonical system layers
2. dependency direction rules
3. capability ownership boundaries

## Decision

0luka adopts the following architecture model:

### Canonical Layers

- Interface Layer
- Module Layer
- System / Services Layer
- Runtime Layer
- Core Layer
- Observability Layer

### Architecture Guardrails

The system adopts three mandatory guardrails:

1. No Cross-Layer Imports
2. Dependency Direction Rule
3. Capability Ownership Rule

### Capability Ownership

Each architectural capability must have exactly one canonical owner.
Canonical owners are defined by the capability documents in docs/architecture/capabilities/.
Implementation paths are references only and do not define ownership.

Initial canonical capabilities are:

- Operator Control
- Policy Governance
- Decision Infrastructure
- Runtime Execution
- Observability Intelligence
- Agent Execution
- Antigravity Module

## Consequences

### Positive

- system structure becomes explicit
- ownership becomes auditable
- future agents can reason about architecture safely
- runtime and governance boundaries become enforceable

### Negative / Cost

- documentation overhead increases
- future components must declare layer and capability before merge
- some existing code may later require refactoring for alignment

## Alternatives Considered

### Alternative A: Keep architecture implicit

Rejected because the repository is already large enough to drift without formal governance.

### Alternative B: Define layers only, no capability ownership

Rejected because ownership ambiguity would remain.

### Alternative C: Capability ownership without layer model

Rejected because ownership depends on stable architectural layers.

## Implementation Notes

The architecture governance stack is now:

```text
0LUKA_SYSTEM_CONSTITUTION.md
        |
        v
0LUKA_LAYER_MODEL.md
        |
        v
0LUKA_ARCHITECTURE_GUARDRAILS.md
        |
        v
Capability ownership docs
```

## Follow-Up

Subsequent architecture work should:

1. enforce capability ownership consistently
2. audit cross-layer imports
3. align runtime implementation with declared ownership
4. maintain ADR history for major structural decisions

## Scope Note

These governance artifacts are docs-only. They do not modify runtime, PM2, launchd, control_tower, or any local Antigravity runtime state.
