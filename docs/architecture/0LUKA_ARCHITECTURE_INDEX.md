# 0luka Architecture Index

## System Overview

0luka is currently a bounded Observability + Reasoning system.

## Architecture Documentation Structure

System overview:

- `0LUKA_FULL_SYSTEM_MAP.md`  
  Comprehensive map of system surfaces.

Topology:

- `0LUKA_SYSTEM_TOPOLOGY.md`  
  Structural architecture diagram of the system.

Evolution model:

- `0LUKA_EVOLUTION_ROADMAP.md`  
  Explains how the system evolved and future phases.

Architecture governance documents:

- `0LUKA_CAPABILITY_MAP.md`  
  Canonical current-state capability contract.

- `0LUKA_DEFINITION_OF_DONE.md`  
  Verification contract for implementation readiness.

Core architectural rules:

- `0LUKA_LAYER_MODEL.md`  
  Canonical system layer definitions (Kernel / Runtime / Modules / Interface / Observability).

- `0LUKA_ARCHITECTURE_INVARIANTS.md`  
  Defines rules that must always remain true.

Architecture safety boundaries:

- `0LUKA_ARCHITECTURE_GUARDRAILS.md`  
  Defines what changes are allowed and forbidden.

Architecture decision framework:

- `0LUKA_ARCHITECTURE_DECISION_RECORDS.md`  
  Framework for documenting architecture decisions.

System constitution:

- `0LUKA_SYSTEM_CONSTITUTION.md`  
  Defines the highest-level architectural principles.

## Reading Order

1. System Constitution
2. Layer Model
3. System Topology
4. System Map
5. Evolution Roadmap
6. Architecture Invariants
7. Architecture Guardrails
8. Architecture Decision Records

## Architecture Stack Diagram

```text
System Constitution
        ↓
Layer Model
        ↓
Architecture Guardrails
        ↓
Architecture Invariants
        ↓
System Topology
        ↓
System Map
        ↓
Evolution Roadmap
        ↓
ADR Framework
```

## Final Statement

These documents collectively define the architectural governance of the 0luka system.
