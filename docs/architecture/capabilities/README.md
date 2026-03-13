# Capability Ownership Model

## Purpose

This document defines the canonical ownership model for architectural capabilities. Each capability has a single source of truth, and execution owners must not redefine capability behavior.

## Ownership Rules

- Each capability has exactly one canonical owner document.
- Execution owners implement within the boundaries defined by the canonical owner.
- Changes require an architecture PR and an ADR update.

## Capability Index

| Capability | Layer | Canonical Owner |
|---|---|---|
| Operator Control | Interface | docs/architecture/capabilities/operator_control.md |
| Policy Governance | Core | docs/architecture/capabilities/policy_governance.md |
| Decision Infrastructure | Core | docs/architecture/capabilities/decision_infrastructure.md |
| Runtime Execution | Runtime | docs/architecture/capabilities/runtime_execution.md |
| Observability Intelligence | Observability | docs/architecture/capabilities/observability_intelligence.md |
| Agent Execution | System / Services | docs/architecture/capabilities/agent_execution.md |
| Antigravity Module | Module | docs/architecture/capabilities/antigravity_module.md |

## Change Authority

All capability changes must follow:
- docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md
