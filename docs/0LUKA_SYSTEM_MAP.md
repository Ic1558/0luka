# 0LUKA SYSTEM MAP

**Version:** 1.1.0 (Operator Grade)  
**Status:** Verified Operational State  
**Context:** Practical guide to repo and runtime paths.

---

## 1. Repository Overview

The 0luka repository contains the runtime kernel, the domain-neutral boundary (interface), and domain-specific logic.

### Repository Topology
```text
0luka/
├── core/                # Runtime Kernel (Deterministic logic)
│   ├── task_dispatcher.py
│   ├── router.py
│   └── ledger.py
│
├── interface/           # Runtime Boundary (I/O)
│   ├── inbox/           # Task ingress (YAML)
│   ├── completed/       # Success archive
│   ├── rejected/        # Failure archive
│   ├── outbox/          # Artifact projection
│   └── operator/        # Mission Control API
│
├── repos/               # Domain Engines
│   └── qs/              # Quantity Surveying Engine
│       ├── src/         # Source code
│       └── tests/       # Verification suite
│
├── tools/               # Operational Tooling
│   └── ops/             # Approval and maintenance scripts
│
├── core_brain/          # Orchestration and coordination
├── observability/       # Activity feeds and provenance
└── docs/                # Architecture and proof reports
```

---

## 2. Runtime Layout Map

The system separates authoritative source code (Repo) from volatile execution data (Runtime Root).

### Path Separation
```text
      (REPOSITORY)                      (EXTERNAL)
      ~/0luka/                      LUKA_RUNTIME_ROOT
         |                                 |
         |                          ~/0luka_runtime/
  interface/                               ├── state/
  ├── inbox/                               │    └── qs_runs/
  ├── completed/                           │
  ├── rejected/                            ├── logs/
  └── outbox/ <---------- (Projection) ----│    └── activity_feed.jsonl
                                           │
                                           └── artifacts/
                                                └── <run_id>/
```

---

## 3. Control Flow: Dispatcher Loop

The system operates on a continuous watch loop. Task progression is strictly forward-moving.

```text
Dispatcher Loop (while True):

    1. SCAN interface/inbox/*.yaml
           ↓
    2. DISPATCH_ONE(task)
           ↓
    3. ROUTER.RESOLVE(intent)  --> (Match against Job Registry)
           ↓
    4. APPROVAL_GATE.CHECK()   --> (Manual check or Auto-pass)
           ↓
    5. EXECUTION_ADAPTER.RUN() --> (Trigger Domain Engine)
           ↓
    6. RUNTIME_SIDECAR.UPDATE()--> (Authoritative State Write)
           ↓
    7. MOVE FILE --> interface/completed/ OR interface/rejected/
```

---

## 4. Artifact Directory Structure

Artifacts produced by domain handlers are isolated by `run_id`.

### Artifacts Layout
```text
~/0luka_runtime/artifacts/
    └── <run_id>/
        ├── boq.json
        ├── cost_estimate.xlsx
        └── report.pdf
```
**Rule:** `artifact_refs` in the State Sidecar must use relative paths inside the run directory to maintain storage abstraction.

---

## 5. Truth Sources vs. Projections

| Type | Components | Authority Level |
| :--- | :--- | :--- |
| **Authoritative Truth** | Runtime State Sidecar, interface/inbox | **Authoritative Source** |
| **Domain Logic** | repos/qs, core/ | Code-level Truth |
| **Projections** | Artifact Outbox, Mission Control API | Read-Model View |
| **Audit Trail** | activity_feed.jsonl, logs/ | Historical Record |

---

## 6. QS Engine Placement

The QS Engine is integrated as a plugin to the Core Runtime.
*   **Location:** `repos/qs`
*   **Registry:** Mapped via `core/router.py` to `qs.*` intents.
*   **Execution:** Runs inside the `ExecutionAdapter` logic.
*   **Output:** Standardized `artifact_refs` returned to the Sidecar.

---

## 7. Operator Entry Points

1.  **Submit Task:** Drop YAML into `interface/inbox/`.
2.  **Approve Job:** Use `tools/ops/approve.py` for pending POs.
3.  **Inspect State:** `GET /api/qs_runs` via Mission Control.
4.  **Health Check:** `GET /health` for system status.
5.  **Manual Dispatch:** `python3 core/task_dispatcher.py` for debugging.

---

## 8. Verified vs. Planned

| Verified Now | Planned / Future |
| :--- | :--- |
| Deterministic QS v1 run | Distributed workers (Celery/K8s) |
| File-based state sidecar | SQL/Key-Value State Store |
| Manual Approval CLI | Automated Policy Approvals |
| Local filesystem artifacts | Object Storage (S3/GCS) |

---

## 9. Quick Start Reading Guide

Order of reading for new engineers:
1.  `docs/0LUKA_MASTER_ARCHITECTURE.md`: The core architectural planes.
2.  **`0LUKA_SYSTEM_MAP.md`**: (This file) repo and runtime paths.
3.  `docs/QS_V1_VERIFIED_REPORT.md`: Real-world domain engine proof.
4.  `core/task_dispatcher.py`: The heart of the execution loop.
