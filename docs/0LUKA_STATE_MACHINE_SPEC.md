# 0LUKA Runtime State Machine Specification

**Version:** v1.0  
**Status:** Runtime Contract

---

## 1. Purpose
This document defines the official runtime state machine of the 0luka execution engine to ensure deterministic, auditable, and fail-closed execution for all domain engines.

---

## 2. State Model Overview
Each run progresses through the following lifecycle:
`INGESTED` → `ACCEPTED` → `PENDING_APPROVAL` (optional) → `EXECUTING` → `COMPLETED` → `ARCHIVED`

**Failure paths:**
*   `ACCEPTED` → `REJECTED`
*   `EXECUTING` → `FAILED`

---

## 3. Canonical Runtime States

| State | Description |
| :--- | :--- |
| **INGESTED** | Task detected in inbox |
| **ACCEPTED** | Task passed router validation |
| **PENDING_APPROVAL** | Waiting for operator approval |
| **APPROVED** | Approval granted |
| **EXECUTING** | Handler currently running |
| **COMPLETED** | Execution finished successfully; artifact_refs produced |
| **FAILED** | Handler raised error; execution aborted |
| **REJECTED** | Router or validation rejected task |
| **ARCHIVED** | Final state stored in history (terminal) |

---

## 4. Valid State Transition Graph
```text
INGESTED
   ↓
ACCEPTED
   ├────────────→ REJECTED → ARCHIVED
   │
   ├────────────→ EXECUTING → COMPLETED → ARCHIVED
   │                    │
   │                    └→ FAILED → ARCHIVED
   │
   └────────────→ PENDING_APPROVAL
                         ↓
                      APPROVED
                         ↓
                     EXECUTING
```

---

## 5. Illegal Transitions
The runtime must reject illegal transitions (e.g., `INGESTED` → `EXECUTING` or `ARCHIVED` → `ANY`). These must trigger a runtime integrity error.

---

## 6. Approval Transition Rules
Approval applies only when `job.requires_approval = true`.
*   Allowed: `PENDING_APPROVAL` → `APPROVED` or `REJECTED`
*   Forbidden: `PENDING_APPROVAL` → `EXECUTING` (Approval must occur before execution)

---

## 7. Execution & Artifact Contract
*   Execution begins only when state is `APPROVED` or `ACCEPTED` (if approval not required).
*   Artifacts (`artifact_refs`) may *only* be produced during the transition from `EXECUTING` to `COMPLETED`.
*   Artifact refs must be empty in all other terminal states (`REJECTED`, `FAILED`).

---

## 8. Runtime State Schema (Example)
```json
{
  "run_id": "run_20260309_001",
  "job_type": "qs.po_generate",
  "state": "PENDING_APPROVAL",
  "execution_status": "blocked",
  "requires_approval": true,
  "artifact_refs": [],
  "created_at": "2026-03-09T02:00:00Z"
}
```

---

## 9. State Invariants
1.  **Single Active State:** A run has exactly one state at any time.
2.  **Forward-Only Progress:** Transitions are monotonic; no rollback allowed.
3.  **Auditability:** Every state transition must produce an event in `logs/activity_feed.jsonl`.
