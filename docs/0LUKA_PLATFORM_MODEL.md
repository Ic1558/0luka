# 0LUKA Platform Model

File: `docs/0LUKA_PLATFORM_MODEL.md`  
Version: `v1.0`  
Status: `Platform Definition`

## 1. Purpose

This document defines the platform model of 0luka.

It explains how the system is organized as a runtime platform rather than a standalone application.

The platform model clarifies:
- how runtime execution works
- how domain engines integrate
- how system safety is enforced
- how observability and operations are structured

This document serves as the entry point for understanding the entire 0luka system.

## 2. Platform Overview

0luka is a deterministic runtime platform designed to execute domain engines through a controlled execution path.

The platform enforces:
- deterministic execution
- approval-gated operations
- artifact provenance
- runtime auditability

All workloads run through the runtime control plane.

## 3. Platform Layers

The 0luka platform is composed of four main layers.

```text
Domain Engines
        ↑
Execution Runtime
        ↑
Control Plane
        ↑
Observability + Operations
```

## 4. Runtime Kernel

The runtime kernel is responsible for controlled task execution.

Core components:
- dispatcher
- router
- runtime state sidecar
- approval gate
- execution adapter

Responsibilities:
- task ingestion
- execution routing
- approval enforcement
- state management
- artifact lifecycle

Reference:
- `docs/0LUKA_MASTER_ARCHITECTURE.md`
- `docs/0LUKA_STATE_MACHINE_SPEC.md`

## 5. Domain Engine Layer

Domain engines implement business logic while relying on the runtime kernel for execution control.

Example engine:
- QS Engine (Quantity Surveying)

Capabilities:
- BOQ extraction
- cost estimation
- purchase order generation
- report generation

Domain engines expose execution through a standardized interface.

`run_registered_job(job_type, context)`

All engines must obey platform invariants.

## 6. Control Plane

The control plane governs how execution is allowed to occur.

Components:
- dispatcher
- approval gate
- runtime validator
- runtime guardian

Responsibilities:
- execution authorization
- state integrity verification
- runtime anomaly detection
- automatic recovery

Reference documents:
- `docs/0LUKA_KERNEL_INVARIANTS.md`
- `docs/0LUKA_RUNTIME_VALIDATOR.md`
- `docs/0LUKA_RUNTIME_GUARDIAN.md`

## 7. Observability Layer

Observability provides visibility into runtime behavior.

Components:
- activity event log
- Mission Control dashboard
- runtime health monitoring
- artifact inspection

Primary interface:
- Mission Control

Capabilities:
- view runs
- inspect runtime state
- review artifacts
- monitor system health

Reference:
- `docs/MISSION_CONTROL_V2_SPEC.md`

## 8. Artifact System

Artifacts represent the output of runtime execution.

Artifact rules:
- produced only by handlers
- immutable after completion
- traceable to `run_id`

Artifact flow:

```text
handler
→ runtime state sidecar
→ artifact store
→ projection
→ Mission Control
```

## 9. Safety Model

0luka enforces safety through multiple layers.

```text
Kernel Invariants
        ↓
Runtime State Machine
        ↓
Runtime Validator
        ↓
Runtime Guardian
```

Purpose:
- prevent invalid execution
- detect invariant violations
- recover from runtime anomalies

## 10. Operational Model

The platform is designed to operate continuously.

Runtime processes include:
- dispatcher service
- guardian monitoring
- mission control server
- artifact storage

Deployment reference:
- `docs/0LUKA_DEPLOYMENT_MODEL.md`

Operational procedures:
- `docs/0LUKA_RUNTIME_OPERATIONS.md`
- `docs/0LUKA_RUNBOOK.md`

## 11. Platform Document Map

The 0luka platform documentation is organized as follows.

Architecture:
- `0LUKA_MASTER_ARCHITECTURE.md`
- `0LUKA_SYSTEM_MAP.md`

Platform Laws:
- `0LUKA_KERNEL_INVARIANTS.md`
- `0LUKA_STATE_MACHINE_SPEC.md`

Runtime Verification:
- `0LUKA_RUNTIME_VALIDATOR.md`
- `0LUKA_RUNTIME_GUARDIAN.md`

Operations:
- `0LUKA_RUNTIME_OPERATIONS.md`
- `0LUKA_RUNBOOK.md`
- `0LUKA_DEPLOYMENT_MODEL.md`

Interface:
- `MISSION_CONTROL_V2_SPEC.md`

## 12. Platform Lifecycle

A workload executed on the platform follows this lifecycle.

```text
task ingress
    ↓
dispatcher
    ↓
router validation
    ↓
approval gate
    ↓
handler execution
    ↓
artifact generation
    ↓
runtime state update
    ↓
Mission Control visibility
```

## 13. Platform Evolution

Future capabilities may include:
- multi-engine ecosystem
- distributed workers
- artifact indexing
- advanced analytics
- predictive runtime monitoring

All future expansion must preserve the kernel invariants and state machine contract.

## 14. Platform Principles

The 0luka platform is built on the following principles.

Controlled Execution:
- All workloads must pass through the runtime execution path.

Deterministic Behavior:
- Execution must produce consistent runtime state transitions.

Artifact Integrity:
- Artifacts must be traceable and immutable.

Observability:
- All runtime actions must be auditable.

## Summary

0luka is a runtime execution platform for domain engines.

The platform integrates:
- runtime kernel
- control plane
- domain engines
- observability layer

This model enables the system to operate as a deterministic, auditable, and extensible execution platform.
