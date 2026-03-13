# 0luka Architecture Index

## System Overview

0luka is currently a bounded Observability + Reasoning system.

## Architecture Documentation Structure

System overview:

- `0LUKA_SYSTEM_SELF_MODEL.md`
  High-level system self-model and current positioning.

Topology:

- `0LUKA_SYSTEM_TOPOLOGY.md`
  Structural architecture diagram of the system.

Evolution model:

- `0LUKA_EVOLUTION_ROADMAP.md`
  Explains how the system evolved and future phases.

Architecture governance documents:

- `0LUKA_LAYER_MODEL.md`
  Canonical system layer definitions.

- `0LUKA_ARCHITECTURE_GUARDRAILS.md`
  Defines what changes are allowed and forbidden.

- `capabilities/README.md`
  Canonical capability ownership model and index.

- `0LUKA_CAPABILITY_MAP.md`
  Current-state capability contract and classification.

- `0LUKA_ARCHITECTURE_INVARIANTS.md`
  Defines rules that must always remain true.

- `0LUKA_DEFINITION_OF_DONE.md`
  Verification contract for implementation readiness.

Architecture decision framework:

- `0LUKA_ARCHITECTURE_DECISION_RECORDS.md`
  Framework for documenting architecture decisions.

System constitution:

- `0LUKA_SYSTEM_CONSTITUTION.md`
  Defines the highest-level architectural principles.

## Reading Order

1. System Constitution
2. Layer Model
3. Architecture Guardrails
4. Capability Ownership
5. Architecture Invariants
6. System Topology
7. System Self Model
8. Evolution Roadmap
9. Architecture Decision Records

## Architecture Stack Diagram

```text
System Constitution
        |
Layer Model
        |
Architecture Guardrails
        |
Capability Ownership
        |
Architecture Invariants
        |
System Topology
        |
System Self Model
        |
Evolution Roadmap
        |
ADR Framework
```

## Final Statement

These documents collectively define the architectural governance of the 0luka system.
