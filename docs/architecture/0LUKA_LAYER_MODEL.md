# 0LUKA Layer Model

## Purpose

This document defines the canonical architectural layers of the 0luka system and the allowed dependency direction between them.

## Layers

### Core Layer
- Role: stable primitives, invariants, and governance rules.
- Examples: core/, core/governance/, core/ledger.py
- Constraints: no dependencies on higher layers.

### Runtime Layer
- Role: execution substrate and process supervision.
- Examples: runtime/
- Constraints: no policy decisions and no autonomous control-plane behavior.

### System / Services Layer
- Role: operational services that coordinate runtime execution and system workflows.
- Examples: system/, services/, agents/, control_tower/
- Constraints: must respect policy governance and remain bounded.

### Interface Layer
- Role: human/operator interaction and presentation surfaces.
- Examples: interface/, tools/mission_control.py
- Constraints: read-only by default and no autonomous actions.

### Observability Layer
- Role: telemetry, logs, artifacts, and reporting.
- Examples: observability/, logs/, reports/
- Constraints: read-only; no runtime mutation.

### Module Layer
- Role: optional domain modules and plug-in capability bundles.
- Examples: modules/, plugins/
- Constraints: must integrate through contracts and remain optional.

## Dependency Direction

Allowed dependency directions:
- Interface -> System / Services, Runtime, Core, Observability (read-only)
- System / Services -> Runtime, Core, Observability
- Runtime -> Core, Observability (contracts only)
- Observability -> Core (schemas/contracts only)
- Module -> System / Services, Runtime, Core, Observability (contracts only)

Forbidden dependency directions:
- Core -> Runtime, System / Services, Interface, Module
- Runtime -> System / Services, Interface, Module
- System / Services -> Interface, Module
- Observability -> System / Services, Interface, Runtime, Module
- Any non-module layer -> Module
