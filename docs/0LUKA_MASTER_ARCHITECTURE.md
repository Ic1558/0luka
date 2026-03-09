# 0LUKA MASTER ARCHITECTURE

**Version:** 1.0.0 (Production Blueprint)  
**Status:** Verified Kernel  
**Reference Implementation:** QS Engine v1  

---

## 1. SYSTEM TOPOLOGY & RUNTIME BOUNDARY

The 0luka architecture strictly decouples the core runtime from domain-specific logic. The runtime acts as the immutable orchestrator, while domain engines are stateless execution workers.

### Explicit Runtime Boundary

```text
      [ External Ingress ]
               |
               v
=======================================
        0LUKA RUNTIME KERNEL
=======================================
   Dispatcher / Router
   Runtime State Sidecar
   Approval Gate
   Execution Adapter
   Job Registry
=======================================
               | (Job Context Context via Interface)
               v
      [ Domain Engine Handlers ]
      (e.g., QS Engine, MEP Engine)
```

**Key Principle:** A Domain Engine is *not* the runtime. It is a strictly controlled, deterministic plugin invoked exclusively by the Execution Adapter.

---

## 2. THE THREE ARCHITECTURAL PLANES

The system is decomposed into three distinct operational planes to ensure integrity, scalability, and security.

### A. Control Plane (Routing & Policy)
Manages the request lifecycle, routing, and access control.
*   **Dispatcher / Router:** Parses ingress, assigns Trace/Run IDs, and matches intents against the Job Registry.
*   **Approval Gate:** Enforces synchronous human/policy checks before execution.
*   **State Machine:** Dictates strictly forward-moving state transitions.

### B. Execution Plane (Logic & Generation)
Handles the heavy lifting of domain-specific business logic.
*   **Job Registry:** The whitelist mapping of `intent` -> `handler`. Fail-closed if missing.
*   **Execution Adapter:** Sandboxes the handler execution.
*   **Domain Handlers:** Pure functions that process inputs and emit standardized `artifact_refs`.

### C. Visibility Plane (Truth & Read Models)
Guarantees auditability and projection of state.
*   **Runtime State Sidecar:** The authoritative, immutable log of run history and artifact pointers.
*   **Artifact Outbox:** The projection staging area for completed job data.
*   **Mission Control:** The operational dashboard and API serving `GET /api/qs_runs`.

---

## 3. RUNTIME STATE MACHINE (DUAL EXECUTION PATHS)

The system supports two deterministic execution paths based on policy requirements, ensuring operators understand exactly how a job flows.

```text
[ ingress_received ] ---> (Invalid Schema) ---> [ failed ]
         |
         v
    [ accepted ]
         |
         +-----------------------------+
         |                             |
(Path A: Approval Required)   (Path B: Auto-Execute)
         |                             |
         v                             |
[ pending_approval ]                   |
         |                             |
    (Gate Cleared)                     |
         |                             |
         v                             v
    [ approved ] ---------------> [ execution_allowed ]
                                       |
                                (Execution Logic)
                                       |
                                       v
                                 [ completed ]
```

---

## 4. ARTIFACT TRUTH MODEL & IMMUTABILITY

This is the core integrity invariant of 0luka. Artifacts cannot be fabricated or injected directly into Mission Control.

### Provenance Chain

```text
[ Domain Handler ] --> Produces Raw Files
         |
         v
[ artifact_refs ] ---> SHA-256 Hashes + Relative Paths
         |
         v
[ Runtime Sidecar ] -> Authoritative Source (Immutable)
         |
         v
[ Artifact Outbox ] -> Projection Only
         |
         v
[ Mission Control ] -> Read-Model View
```

### The Anti-Fabrication Rule
1.  **Artifact Immutability:** Once `artifact_refs` are persisted in the Runtime Sidecar, they are strictly immutable.
2.  **Authoritative Source:** The Sidecar is the absolute source of truth.
3.  **Projection Only:** The Outbox is merely a projection; modifying the outbox directly breaks the hash chain and invalidates the artifact in Mission Control.

---

## 5. DOMAIN ENGINE TEMPLATE

Future domain engines must implement the following structure, using QS Engine v1 as the baseline.

### 5.1 Structure
1.  **Registry:** Expose unique `job_types` (e.g., `mep.cost_estimate`).
2.  **Handlers:** Stateless execution functions.
3.  **Artifact Contract:** Strict return type containing `{ run_id, artifacts: [ {id, path, hash} ] }`.
4.  **Runtime Integration:** Must interface strictly via the Execution Adapter.

### 5.2 Job Handler Lifecycle
Every Domain Handler must follow this internal deterministic loop:
1.  `load_context`: Parse inputs provided by the runtime.
2.  `validate_context`: Ensure required files/data exist before starting heavy compute.
3.  `execute_logic`: Run the core domain algorithm (e.g., DXF mapping, pricing).
4.  `produce_artifacts`: Write resulting outputs (JSON, XLSX) to the assigned temporary workspace.
5.  `return artifact_refs`: Generate and return the checksum-verified contract back to the runtime.

---

## 6. FROZEN KERNEL INTERFACES

If these four interfaces remain locked, the system can evolve infinitely without breaking.

1.  **Execution Interface:** `run_registered_job(job_type, context)`
2.  **Artifact Contract:** The `artifact_refs` return schema (must include hashes).
3.  **Sidecar Schema:** The schema for appending states to the Runtime State Sidecar.
4.  **Projection Schema:** The API response format for Mission Control (`GET /api/runs/{id}`).

---

## 7. FUTURE EXTENSION POINTS

The architecture is designed to accommodate the following capabilities without modifying the frozen kernel interfaces:

### 7.1 Event Stream / Audit Pipeline
Leveraging existing `activity_feed.jsonl` and phase events to power:
*   Real-time Operational Monitoring.
*   Security Audit Analytics.
*   Webhook event broadcasting.

### 7.2 Artifact Storage Abstraction
Migrating the physical layer of the `Artifact Outbox`:
*   *Current:* Local Filesystem.
*   *Future:* S3-compatible Object Storage or Distributed Artifact Stores, purely by swapping the storage driver behind the Sidecar -> Outbox projection step.

### 7.3 Distributed Execution & High Volume
Scaling the Execution Plane:
*   The `Dispatcher` can assign `execution_allowed` jobs to remote worker queues.
*   As long as remote workers fulfill the `Job Handler Lifecycle` and return standard `artifact_refs` to the centralized Sidecar, the integrity remains unbroken.
