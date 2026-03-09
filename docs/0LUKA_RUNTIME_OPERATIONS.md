# 0LUKA Runtime Operations Guide

**Production Operations Manual**  
**For:** 0luka Runtime + QS Engine v1

---

## 1. Overview
0luka is a deterministic runtime platform that executes domain engines through a controlled runtime path. Operators interact with the system through:
*   Task ingress
*   Approval control
*   Mission Control visibility
*   CLI runtime tools

All runtime activity is mediated by the dispatcher + runtime sidecar state.

---

## 2. Runtime Components

### Core Runtime
**Location:** `core/`

| Component | Role |
| :--- | :--- |
| `task_dispatcher` | Task ingestion + execution loop |
| `router` | Task intent resolution |
| `approval_gate` | Approval gating |
| `execution_adapter` | Domain engine invocation |
| `runtime_sidecar` | Authoritative runtime state |

### Domain Engine
**Current verified engine:** `repos/qs/`  
**Jobs:** `qs.boq_extract`, `qs.cost_estimate`, `qs.po_generate`, `qs.report_generate`  
**Execution entrypoint:** `run_registered_job(job_type, context)`

---

## 3. Runtime Directory Layout
Runtime state lives outside the repo in `LUKA_RUNTIME_ROOT`.

**Typical structure:**
```text
~/0luka_runtime/
├── state/
│   └── qs_runs/
│       └── <run_id>.json
├── artifacts/
│   └── <run_id>/
│       ├── boq.json
│       ├── cost_estimate.xlsx
│       └── report.pdf
└── logs/
    └── activity_feed.jsonl
```

---

## 4. Interface Queue
Task ingress occurs through the interface queue inside the repository.

**Location:** `0luka/interface/`
```text
interface/
├── inbox/
├── completed/
├── rejected/
└── outbox/
```

---

## 5. Dispatcher Runtime Loop
The dispatcher must always be running for tasks to execute.

**Runtime behavior:**
1.  Scan `interface/inbox/*.yaml`
2.  `dispatch_one(task)`
3.  `router.resolve(intent)`
4.  `approval_gate.check()`
5.  `execution_adapter.run()`
6.  `runtime_sidecar.update()`
7.  Move file → `completed/` or `rejected/`

---

## 6. Task Execution Lifecycle
1.  Task ingress
2.  Dispatcher acceptance
3.  Runtime state initialization
4.  Approval gate evaluation
5.  Handler execution
6.  Artifact production
7.  Runtime state update
8.  Outbox projection
9.  Mission Control visibility

---

## 7. Approval Workflow
Certain jobs (e.g., `qs.po_generate`) require approval before execution.

**Lifecycle:** `accepted` → `pending_approval` → `approved_by_operator` → `execution`

**Approve via CLI:**
`python3 tools/ops/qs_approval_runtime.py approve <run_id>`

**Reject via CLI:**
`python3 tools/ops/qs_approval_runtime.py reject <run_id>`

---

## 8. Artifact Handling
Handlers return `artifact_refs` (e.g., `{"artifact_type": "boq", "path": "artifacts/<run_id>/boq.json"}`).
*   Stored under `~/0luka_runtime/artifacts/<run_id>/`
*   No fabricated artifacts allowed.
*   No mutation after persistence.
*   Runtime sidecar is authoritative.

---

## 9. Mission Control Visibility
Exposes runtime state through read-only APIs (`/api/qs_runs`, `/api/qs_runs/{run_id}`). Mission Control must never mutate runtime state.

---

## 10. Monitoring
*   **Check runs:** `ls ~/0luka_runtime/state/qs_runs/`
*   **Inspect run state:** `cat ~/0luka_runtime/state/qs_runs/<run_id>.json`
*   **Inspect artifacts:** `ls ~/0luka_runtime/artifacts/<run_id>/`
*   **Check activity log:** `tail -f ~/0luka_runtime/logs/activity_feed.jsonl`

---

## 11. Debugging

### Task stuck in inbox
*   **Causes:** Dispatcher not running, router rejection, or schema validation failure.
*   **Check:** `interface/inbox/`, `interface/rejected/`

### Execution blocked
*   **Cause:** Approval required.
*   **Check:** `approval_state`, `execution_status`

### Artifact missing
*   **Causes:** Handler failure, artifact path error.
*   **Check:** Run state JSON, `logs/activity_feed.jsonl`

---

## 12. Operational Commands
*   **Start dispatcher:** `python3 core/task_dispatcher.py`
*   **Approve run:** `python3 tools/ops/qs_approval_runtime.py approve <run_id>`
*   **Reject run:** `python3 tools/ops/qs_approval_runtime.py reject <run_id>`
*   **Inspect runs:** `ls ~/0luka_runtime/state/qs_runs`

---

## 13. Safety Guarantees
*   **Fail closed:** Unknown job_type, malformed context, or missing approval blocks execution.
*   **Artifact integrity:** Refs originate from handlers only; Sidecar is the source of truth.

---

## 14. Recovery Procedures
If runtime is interrupted, restart the dispatcher. Runs remain safe because state is persisted and artifacts are immutable.

---

## 15. Operational Model
*   **Deterministic execution:** Same input → same runtime state.
*   **Controlled path:** All runs go through dispatcher + approval gate.
*   **Artifact truth chain:** Handler → Runtime State → Outbox → Mission Control.

---

## 16. Operator Checklist
*   Dispatcher running
*   Runtime root available
*   Artifact directory writable
*   Approval CLI accessible
*   Mission Control reachable

---

## 17. Related Documentation
1.  `docs/0LUKA_MASTER_ARCHITECTURE.md`
2.  `docs/0LUKA_SYSTEM_MAP.md`
3.  `docs/review/QS_v1_VERIFIED.md`
4.  `docs/review/QS_v2_ROADMAP.md`
