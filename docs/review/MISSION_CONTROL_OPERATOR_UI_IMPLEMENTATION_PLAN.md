# Mission Control Operator UI Implementation Plan

## Current UI Baseline
The current Mission Control interface (`mission_control.html`) is a functional but legacy-structured dashboard. 
- **Existing Panels:** System Health, Operator Status, Bridge Status, Activity Feed, Alerts, Remediation History, Approval Workflow.
- **Data Fetching:** Multiple independent `setInterval` calls (mostly 5s) hitting granular endpoints.
- **Frontend Logic:** Native JS with `Template` interpolation on the backend and manual `innerHTML` manipulation on the frontend.
- **Gaps:** Lacks dedicated visualization for the Kernel Verification Chain, detailed Guardian Action history, and the new consolidated Dashboard API.

## Target Dashboard Layout
The new dashboard will transition to using the `/api/operator/dashboard` aggregation endpoint as its primary source of truth.

| Panel | Title | Data Path | Display Fields | Refresh (S) |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Kernel Health** | `.kernel` | Status, Env Present, Artifacts | 10 |
| **2** | **Verification** | `.verification` | Trace ID, Verdict, Timestamp | 15 |
| **3** | **Guardian Interventions**| `.guardian` | Action, Reason, Run ID | 15 |
| **4** | **Remediation Queue** | `.remediation_queue` | Item ID, Lane, Action, State | 5 |
| **5** | **Approvals & Lanes** | `.approval_state` | Lane ID, Status, Expiry | 10 |
| **6** | **Consistency (Drift)** | `.policy_drift` | Log/Env Consistency Flags | 30 |
| **7** | **QS Operations** | `.qs_overview` | Run Summary, Recent Project IDs | 20 |

## Component Model
We will adopt a minimal component pattern within the existing `script` block or a modularized JS file:
- `DashboardShell`: Manages the polling loop and top-level error state.
- `HealthCard`: Visual indicators for Kernel/System health.
- `VerificationTable`: Lists task-level verification results.
- `ActionList`: Renders both Guardian and Remediation queue items with severity styling.
- `LanePanel`: Interactive view of approval status and expiry.

## Data Mapping
The frontend will map the consolidated `/api/operator/dashboard` response directly to UI elements:
- `data.kernel` → Header health badges.
- `data.verification` → "Verified Tasks" table.
- `data.guardian` → "Guardian Log" (styled as alerts).
- `data.remediation_queue` → "Action Queue" list.
- `data.approval_state.lanes` → Individual lane status cards.

## Polling and Refresh Strategy
- **Primary Source:** `GET /api/operator/dashboard`
- **Fallback Interval:** 10s (Global default for the aggregate request).
- **Loading UI:** Skeleton placeholders or opacity reduction during active fetch.
- **Error Handling:** Global banner if the server is unreachable; panel-level "No Data" indicators for loader failures.

## Read-Only Guarantees
- **Observational Interface:** All dashboard components will use strictly passive rendering from the JSON state.
- **Action Decoupling:** Existing action buttons (Approve/Reject) will remain independent of the read-model refresh loop to prevent UI flickering.

## Suggested Implementation Order
1. **Wire Aggregate API:** Update `script` to call `/api/operator/dashboard` instead of individual panel refreshes.
2. **Refactor Core Panels:** Move `Activity` and `Remediation` logic to consume the new aggregate schema.
3. **Implement Kernel Panels:** Add new HTML sections for `Kernel Status` and `Verification History`.
4. **Final Styling:** Normalize CSS themes across the new panels.

## Non-Claims
- UI phase will **not** implement user authentication or roles.
- UI phase will **not** modify existing backend route logic.
- UI phase will **not** provide historical data graphing/trending (state-at-rest only).
