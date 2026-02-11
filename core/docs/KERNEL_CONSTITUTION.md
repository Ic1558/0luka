# OPAL KERNEL CONSTITUTION

**Status:** 👑 SUPREME LAW
**Enforcement:** Mandaory. No other document may override this.
**Version:** 1.0 (Bound to OPAL Kernel v1.3+)

---

## 1. The Kernel-as-ABI Principle
The **Kernel** is not the code. The Kernel is the **ABI** (Application Binary Interface).
- The ABI consists of: **Contracts**, **Schemas**, **Semantics**, and **Lifecycle Laws**.
- Implementation details (Server, Client, Worker) must bend to fit the Kernel. The Kernel never bends to fit implementation convenience.

## 2. The Byte-Parity Rule
- The `core/contracts/v1/opal_api.openapi.json` file is the **Source of Truth (SOT)**.
- The Server MUST serve an `/openapi.json` that is **byte-equivalent** (or functionally identical) to the SOT.
- Any deviation meant that the Server is **not** running the Kernel.

## 3. Job Lifecycle Law
- A Job MUST transition deterministically: `queued` → `running` → `succeeded` OR `failed`.
- **Transitions**: Atomic. No ambiguous states.
- **Timestamps**: `created_at`, `started_at`, `completed_at` are mandatory for all terminal jobs.
- **Crash Recovery**: "Zombie" jobs (running during a crash) MUST be auto-failed upon recovery.

## 4. Provenance Requirement
- Every execution MUST produce a `RunProvenance`.
- **Engine**: The executor name must be explicit (e.g., `nano_banana`, `mock_engine`).
- **Input Checksum**: The inputs must be hashed to prove what was run.
- **Version**: The engine version must be recorded.

## 5. Engine Agnosticism Rule
- The **Worker Logic** MUST NOT contain `if engine == "x"` logic for core execution flow.
- Engine specifics MUST be isolated in **Adapters**.
- To change an engine, modifying the Worker core is **Forbidden**.

## 6. Versioning Rules
- **Breaking Change** to ABI = **Major Kernel Bump**.
- **New Feature** (Additive) = **Minor Kernel Bump**.
- **Fix** (No ABI change) = **Patch**.
- **Implementation Change** (Server/Client) = Does **NOT** change Kernel Version (use `server-vX` tags).

---
*To amend this Constitution, you must modify `core/docs/KERNEL_CONSTITUTION.md` and pass a Governance Review.*
