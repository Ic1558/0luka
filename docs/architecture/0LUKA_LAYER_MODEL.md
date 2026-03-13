# 0LUKA Layer Model

## Purpose

This document defines the canonical layer architecture of the 0luka system.

Its goal is to prevent architectural drift by enforcing:
- clear layer boundaries
- deterministic dependency direction
- stable ownership of runtime responsibilities

All system components must belong to exactly one layer defined here.

---

## Layer Stack

The 0luka architecture consists of six layers.

```text
Operator
   |
Interface
   |
Modules
   |
Runtime
   |
Core
   |
Observability
```

Dependency direction is strictly downward only.

Higher layers may depend on lower layers.
Lower layers may never depend on higher layers.

---

## Layer Definitions

### 1. Interface Layer

Location:

interface/

Role:

Human interaction surface for operators and developers.

Responsibilities:
- Mission Control
- dashboards
- operator approval / rejection
- review panels
- cockpit interfaces
- simulation surfaces
- proposal authoring

Examples:

interface/operator/
interface/operator/mission_control/

Rules:

Interface must not contain business logic or system survival logic.

The system must continue running correctly if the Interface layer is not running.

---

### 2. Modules Layer

Location:

modules/

Role:

Domain capability packs.

Modules implement domain intelligence or domain-specific behaviors.

Examples:

modules/antigravity/
modules/antigravity/intelligence/
modules/antigravity/realtime/
modules/antigravity/connectors/

Responsibilities:
- market intelligence
- quant models
- strategy logic
- connectors to external services
- domain-specific algorithms

Rules:

Modules may depend on:
- runtime
- core
- observability

Modules must not own system governance or policy law.

Modules must not manage system lifecycle or process supervision.

---

### 3. Runtime Layer

Location:

runtime/

Role:

Always-on system execution layer.

Responsibilities:
- long-running services
- scheduled jobs
- ingestion pipelines
- service lifecycle
- runtime supervision
- health checks
- runtime state

Examples:

runtime/services/
runtime/supervisors/
runtime/state/

Runtime owns:
- process lifecycle
- service startup
- restart discipline
- runtime orchestration

Runtime must not define governance rules or policy law.

---

### 4. Core Layer

Location:

core/

Role:

Kernel of the 0luka system.

Core defines system law and invariants.

Responsibilities:
- governance rules
- policy logic
- decision contracts
- execution contracts
- state schemas
- kernel dispatch
- reconciliation logic

Examples:

core/governance/
core/policy/
core/contracts/
core/runtime_kernel/

Core must remain:
- deterministic
- minimal
- stable

Core must not depend on:
- runtime
- modules
- interface

---

### 5. Observability Layer

Location:

observability/

Role:

System evidence and telemetry.

Responsibilities:
- logs
- artifacts
- ledgers
- reports
- metrics
- policy statistics
- audit records

Examples:

observability/logs/
observability/artifacts/
observability/reports/
observability/ledgers/

Observability stores evidence of what happened, but does not control system behavior.

Observability must not contain business logic or execution logic.

---

### 6. Tools Layer

Location:

tools/

Role:

Operational scripts and maintenance utilities.

Examples:

tools/deploy/
tools/ops/
tools/maintenance/

Tools may interact with any layer but must not become runtime dependencies.

Tools are not part of the system kernel.

---

## Dependency Direction Rule

Dependencies may only move downward.

Valid dependency direction:

Interface -> Modules -> Runtime -> Core -> Observability

Forbidden dependencies:

Core -> Runtime
Core -> Modules
Core -> Interface

Runtime -> Modules
Runtime -> Interface

---

## Verification Layer Exception

Test and verification modules are allowed to access multiple layers.

Location:

core/verify/
tests/

Verification code may depend on:
- interface
- modules
- runtime
- core
- observability

This exception applies only to test code.

Runtime code must never rely on verification modules.

---

## System Survival Rule

Any component required for the system to continue running after reboot must belong to one of these layers:

core
runtime
observability

Modules and Interface must never contain logic required for system survival.

---

## Canonical System Principle

The system architecture is kernel-centric.

0luka = kernel
modules = capability packs
interface = operator surface

Subsystems such as Antigravity must exist as modules under the 0luka kernel, not as host systems.

---

## Architectural Invariants

The following rules must never be violated:
1. Core remains deterministic.
2. Runtime owns process lifecycle.
3. Modules implement domain capabilities only.
4. Interface contains no system survival logic.
5. Observability remains append-only evidence storage.
6. Dependency direction always flows downward.
7. Kernel governance is never bypassed by modules or runtime services.

---

## Consequence of Violation

Violations of the layer model introduce:
- architecture entanglement
- governance bypass
- hidden runtime coupling
- uncontrolled autonomy expansion

Any violation must be treated as an architecture defect.

---

## Document Status

Status:

Canonical architecture contract

Changes to this document require architecture review approval.
