# ARCHITECTURE NOTE — OPAL Kernel Model

**Status:** Non-Authoritative (Explanatory)
**Rule:** This document does NOT override the Kernel Constitution.

---

## 1. Mental Model

```mermaid
graph TD
    Client[Client (Design Lane UI)] -->|ABI (OpenAPI vX.Y.Z)| Kernel
    Kernel[Kernel (contracts + schemas + semantics)] --> Server
    Server[Server (OPAL API)] --> Worker
    Worker[Worker (engine-agnostic)] --> Adapter
    Adapter[Engine Adapter] --> Engine[Engine (nano_banana / mock)]
```

---

## 2. Core Principles

### 1. Kernel ≠ Code
Kernel is:
- Contracts
- Schemas
- Semantics
- Lifecycle Law

Code is just an implementation detail.

### 2. ABI Stability > Feature Velocity
- Every breaking change → **Bump Kernel**.
- Server/Client must declare kernel compatibility.

### 3. Engine Isolation
- Worker does not know the internal engine.
- Only the **Adapter** knows.

### 4. Observability is Mandatory
- Timestamps
- Provenance
- Checksums
- Structured logs

---
