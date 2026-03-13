# 0LUKA Architecture Guardrails

## Purpose

This document defines the minimum architectural rules that prevent architecture entanglement, runtime fragility, and agent ownership drift. It is governance-first and evidence-bound.

Architecture authority is defined by:

- `docs/architecture/0LUKA_ARCHITECTURE_CONTRACT.md`
- `docs/architecture/0LUKA_ARCHITECTURE_INVARIANTS.md`

Read-only enforcement command:

- `tools/architecture_guard.sh`

## Layer Model

### Interface Layer
- Role: human/operator interaction and presentation.
- Examples: interface/operator/, tools/mission_control.py, tools/ops/operator_*
- Allowed dependencies: System / Services Layer, Runtime Layer, Core Layer, Observability Layer (read-only)

### System / Services Layer
- Role: operational services, orchestration, and runtime coordination.
- Examples: system/, runtime/, services/, control_tower/, agents/
- Allowed dependencies: Runtime Layer, Core Layer, Observability Layer

### Runtime Layer
- Role: execution substrate and process supervision.
- Examples: runtime/
- Allowed dependencies: Core Layer, Observability Layer (contracts only)

### Core Layer
- Role: stable system primitives and invariants.
- Examples: core/, core/governance/, core/ledger.py, core/task_dispatcher.py, core/run_provenance.py
- Allowed dependencies: none

### Observability Layer
- Role: telemetry, logs, artifacts, and reporting.
- Examples: observability/, logs/, telemetry/, reports/
- Allowed dependencies: Core Layer (schemas/contracts only)

### Module Layer
- Role: optional domain modules and plug-in capability bundles.
- Examples: modules/, plugins/
- Allowed dependencies: System / Services Layer, Runtime Layer, Core Layer, Observability Layer (contracts only)

---

## Rule 1 — No Cross-Layer Imports

### Purpose
Prevent architecture entanglement by enforcing directionality between layers.

### Rule Definition
Imports may only flow inward/downward toward more stable layers. Cross-layer or upward imports are forbidden.

### Allowed Patterns
- Interface -> System / Services
- Interface -> Runtime
- Interface -> Core
- Interface -> Observability (read-only)
- System / Services -> Runtime
- System / Services -> Core
- System / Services -> Observability
- Runtime -> Core
- Runtime -> Observability (contracts only)
- Observability -> Core (schemas/contracts only)
- Module -> System / Services
- Module -> Runtime
- Module -> Core
- Module -> Observability (contracts only)

### Forbidden Patterns
- Core -> Runtime
- Core -> System / Services
- Core -> Interface
- Core -> Module
- Runtime -> System / Services
- Runtime -> Interface
- Runtime -> Module
- System / Services -> Interface
- System / Services -> Module
- Observability -> System / Services or Interface
- Observability -> Runtime or Module

### Violation Detection
- Scan Python imports (import/from) and map each file to a layer.
- Flag any import that crosses upward or sideways into less stable layers.
- Flag any dependency on a Module from non-module layers.

### Fix Strategies
- Move shared logic downward into Core.
- Invert dependency via an interface in a stable layer.
- Replace direct import with data contracts (events, JSON, schema).
- Mark non-core usage as read-only or optional.

---

## Rule 2 — Dependency Direction Rule

### Purpose
Prevent runtime fragility by ensuring critical paths do not depend on optional tooling.

### Rule Definition
Runtime-critical code may only depend on components that are equal or lower in operational criticality.

### Allowed Patterns
- Tier A (runtime-critical) -> Tier A
- Tier B (operational support) -> Tier A or Tier B
- Tier C (tooling/advisory) -> Tier A, Tier B, or Tier C

### Forbidden Patterns
- Tier A -> Tier C
- Tier A -> optional Tier B

### Violation Detection
- Classify modules by tier and map dependencies.
- Flag any Tier A dependency on Tier C or optional tooling.

### Fix Strategies
- Move shared logic into Tier A (Core) where required.
- Invert dependency (define interface in Tier A).
- Replace direct dependency with a data contract.
- Make optional dependencies explicitly guarded.

---

## Rule 3 — Capability Ownership Rule

### Purpose
Prevent agent ownership drift by enforcing a single source of truth per capability.

### Rule Definition
Every architectural capability must have exactly one canonical owner. Other components may support or observe, but must not redefine the capability.

### Allowed Patterns
- One canonical owner per capability.
- Support components read/validate/report without redefining ownership.

### Forbidden Patterns
- Multiple documents defining the same capability as canonical.
- Execution owners redefining capability behavior without the canonical owner.

### Violation Detection
- Identify capabilities without a single canonical owner.
- Flag multiple files acting as parallel sources of truth.

### Fix Strategies
- Declare the owner explicitly in architecture docs.
- Move shadow logic under the owner or downgrade to support.
- Replace duplicate definitions with references.

### Capability Ownership Model

| Capability | Canonical Owner | Execution Owner | Evidence Source | Change Authority |
|---|---|---|---|---|
| Operator Control | docs/architecture/capabilities/operator_control.md | Interface operator surfaces | docs/architecture/0LUKA_SYSTEM_CONSTITUTION.md | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Policy Governance | docs/architecture/capabilities/policy_governance.md | Core policy services | docs/architecture/0LUKA_ARCHITECTURE_INVARIANTS.md | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Decision Infrastructure | docs/architecture/capabilities/decision_infrastructure.md | Core decision pipeline | docs/architecture/0LUKA_ARCHITECTURE_INVARIANTS.md | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Runtime Execution | docs/architecture/capabilities/runtime_execution.md | Runtime supervisors | docs/architecture/0LUKA_SYSTEM_CONSTITUTION.md | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Observability Intelligence | docs/architecture/capabilities/observability_intelligence.md | Observability tooling | docs/architecture/0LUKA_OBSERVABILITY_INTELLIGENCE.md | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Agent Execution | docs/architecture/capabilities/agent_execution.md | System services | docs/architecture/0LUKA_SYSTEM_CONSTITUTION.md | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Antigravity Module | docs/architecture/capabilities/antigravity_module.md | Module runtime (optional) | docs/architecture/0LUKA_ARCHITECTURE_INVARIANTS.md | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Runtime supervision | docs/architecture/mac-mini-supervisor-decision.md | Live supervisor (PM2 now, launchd target) | g/reports/mac-mini/runtime_topology.md | docs/architecture/mac-mini-migration-plan.md |
| Mission Control API surface | interface/operator/mission_control_server.py | Mission Control server process | core/verify/test_mission_control_server.py | docs/architecture/phases/phase-11.0-completion.md |
| Policy intelligence | tools/ops/policy_intelligence.py | Mission Control policy endpoints | core/verify/test_policy_intelligence.py | docs/architecture/0LUKA_SYSTEM_CONSTITUTION.md |
| Runtime inventory & topology | docs/architecture/mac-mini-runtime-inventory.md | tools/ops/runtime_inventory.zsh | g/reports/mac-mini/runtime_topology.md | docs/architecture/mac-mini-migration-plan.md |

---

## Architecture Safety Summary

Together, these three rules prevent:
- architecture entanglement (No Cross-Layer Imports)
- runtime fragility (Dependency Direction Rule)
- agent chaos / ownership drift (Capability Ownership Rule)

This guardrail set is the minimum required to keep the 0luka architecture coherent as the system scales.
