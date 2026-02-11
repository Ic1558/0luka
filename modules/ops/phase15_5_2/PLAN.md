<!--
Step 15501 Plan: Phase 15.5.2 Heartbeat
-->
# Phase 15.5.2: Timeline Heartbeat Emit Hook Plan

## Objective
Add a minimal, non-blocking hook to `core/task_dispatcher.py` that emits heartbeat events to the task timeline. This ensures dispatcher activity (start/end) is observable without relying on external services or changing gate logic.

## Scope
-   **Modify**: `core/task_dispatcher.py`
-   **New Test**: `core/verify/test_phase15_5_2_timeline_heartbeat.py`
-   **Docs**: `modules/ops/phase15_5_2/{PLAN,DIFF,VERIFY}.md`

## Implementation Details
1.  **Hook Logic**:
    -   In `dispatch_one`, emit `heartbeat.dispatcher` event at start (status: start).
    -   In `dispatch_one`, emit `heartbeat.dispatcher` event at end (status: committed|rejected|error).
    -   All emissions must be wrapped in `try/except` to ensure non-fatal behavior.
2.  **Payload**:
    -   `event`: "heartbeat.dispatcher"
    -   `task_id`: <current_task_id>
    -   `status`: start | committed | rejected | error
    -   `source`: "dispatcher"
    -   `ts_utc`: (handled by emit_event)
3.  **Use Existing Mechanism**:
    -   Import `emit_event` from `core.timeline`.

## Verification Strategy
-   Run `pytest core/verify/test_phase15_5_2_timeline_heartbeat.py` to confirm emissions occur and failures are strictly non-fatal.
