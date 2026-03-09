# Mission Control v2 Specification

**Purpose:** Operational dashboard for 0luka runtime.

---

## 1. Core Goals
Mission Control v2 must provide:
*   Runtime observability
*   Run inspection
*   Approval management
*   Artifact navigation
*   System health

---

## 2. Primary Screens

### Dashboard
*   **Widgets:** Active runs, Pending approvals, Recent failures, Artifact generation rate, Dispatcher status.

### Runs Table
*   **Columns:** `run_id`, `job_type`, `project_id`, `runtime_state`, `execution_status`, `approval_state`, `artifacts`, `created_at`.
*   **Data source:** `/api/qs_runs`

### Run Detail Page
*   **Content:** Full runtime state, artifact refs, approval history, execution timeline.
*   **Endpoint:** `/api/qs_runs/{run_id}`

### Approval Queue
*   **List:** `pending_approval` runs.
*   **Actions:** Approve (`POST /api/approve_run`), Reject (`POST /api/reject_run`).

### Artifact Browser
*   **Structure:** `artifacts/<run_id>/`
*   **Features:** Download, preview, metadata view.

---

## 3. System Health Panel
*   **Indicators:** Dispatcher alive, runtime root accessible, artifact storage healthy, API status.

---

## 4. Event Feed
*   **Source:** `activity_feed.jsonl`
*   **Events:** Run started, completed, approval event, failure event.

---

## 5. Future Expansion
*   Multi-engine support
*   Distributed workers
*   Artifact search
*   Audit analytics
