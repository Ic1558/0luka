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

- `0LUKA_ARCHITECTURE_CONTRACT.md`
  Binding architecture contract and source-of-truth priority.

- `0LUKA_LAYER_MODEL.md`
  Canonical system layer definitions.

- `0LUKA_LAYER_CONTRACT.md`
  Authoritative path-to-layer mapping contract for governance/tooling checks.

- `0LUKA_ARCHITECTURE_GUARDRAILS.md`
  Defines what changes are allowed and forbidden.

- `antigravity_runtime_state.md`
  Verified Antigravity runtime state, drift classification, and canonical
  runtime ownership.

- `runtime/ANTIGRAVITY_RUNTIME_REMEDIATION_PLAN_2026-03-13.md`
  Canonical remediation plan for evidence-backed Antigravity runtime drift.

- `runtime/ANTIGRAVITY_RUNTIME_EXECUTION_PLAN_2026-03-13.md`
  Supervised execution sequence for approved runtime remediation.

- `runtime/ANTIGRAVITY_RUNTIME_EXECUTION_APPROVAL_2026-03-13.md`
  Explicit approval boundary record for runtime remediation execution.

- `../runtime/antigravity/`
  Canonical Antigravity runtime Phase R1 scaffolding subtree.

- `../runtime/antigravity/executor/ANTIGRAVITY_EXECUTOR_CONTRACT.md`
  Executor boundary contract for non-approved default runtime posture.

- `../runtime/antigravity/runtime_state/antigravity_runtime_state.py`
  Local typed runtime state model used by the executor scaffold.

- `../runtime/antigravity/artifacts/antigravity_blocker.py`
  Structured blocker artifact model for runtime analysis.

- `../runtime/antigravity/artifacts/antigravity_evidence.py`
  Structured evidence reference artifact model for runtime analysis.

- `../runtime/antigravity/artifacts/antigravity_plan.py`
  Structured remediation plan artifact model for runtime analysis.

- `capabilities/README.md`
  Canonical capability ownership model and index.

- `0LUKA_CAPABILITY_MAP.md`
  Current-state capability contract and classification.

- `0LUKA_ARCHITECTURE_INVARIANTS.md`
  Defines rules that must always remain true.

- `../tools/architecture_guard.sh`
  Read-only architecture drift detector for governance enforcement.

- `0LUKA_DEFINITION_OF_DONE.md`
  Verification contract for implementation readiness.

Architecture decision framework:

- `0LUKA_ARCHITECTURE_DECISION_RECORDS.md`
  Framework for documenting architecture decisions.

- `adr/ADR-001-capability-ownership-and-layer-model.md`
  First resolved ADR: capability ownership and layer model.

- `adr/ADR-UNRESOLVED-INDEX.md`
  Tracking index for known, unresolved architecture decisions.

System constitution:

- `0LUKA_SYSTEM_CONSTITUTION.md`
  Defines the highest-level architectural principles.

## Reading Order

1. System Constitution
2. Architecture Contract
3. Layer Model
4. Architecture Guardrails
5. Capability Ownership
6. Architecture Invariants
7. System Topology
8. System Self Model
9. Evolution Roadmap
10. Architecture Decision Records

## Architecture Stack Diagram

```text
System Constitution
        |
Architecture Contract
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
