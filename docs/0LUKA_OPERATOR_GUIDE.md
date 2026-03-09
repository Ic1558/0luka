# 0LUKA Operator Guide

File: `docs/0LUKA_OPERATOR_GUIDE.md`  
Version: `v1.0`  
Status: `Production Operations Manual`

## 1. Purpose

This guide provides operational instructions for managing and maintaining the 0luka runtime platform in a production environment.

The operator guide explains how to:
- start the platform
- monitor runtime health
- inspect execution runs
- handle incidents
- recover from failures
- perform maintenance

This document is intended for system operators and maintainers.

## 2. System Overview

The 0luka platform is a deterministic runtime environment that executes domain engines through a controlled execution pipeline.

Execution flow:

```text
task ingress
 → dispatcher
 → router validation
 → run creation
 → approval gate
 → handler execution
 → artifact generation
 → projection
 → Mission Control visibility
```

Reference:
- `docs/0LUKA_EXECUTION_MODEL.md`

## 3. Core Runtime Services

The following services must be operational.

| Service | Purpose |
|---|---|
| dispatcher | accepts and schedules tasks |
| runtime state | manages run lifecycle |
| validator | verifies runtime invariants |
| guardian | protects runtime stability |
| mission control | operator visibility |

Operators must ensure these services remain active.

## 4. Starting the Platform

Typical startup sequence:
1. start dispatcher
2. start runtime services
3. start guardian
4. start Mission Control

Example commands:

```bash
launchctl start com.0luka.dispatcher
launchctl start com.0luka.guardian
launchctl start com.0luka.mission_control
```

Verify services are running.

## 5. Runtime Health Check

Operators should regularly inspect system health.

Key checks:
- dispatcher process running
- task queue progressing
- runs completing normally
- guardian active

Example command:

```bash
ps aux | grep dispatcher
```

Mission Control dashboard provides runtime status.

## 6. Monitoring Runs

Operators can inspect execution runs via API.

Example endpoints:
- `/api/qs_runs`
- `/api/qs_runs/{run_id}`

Run information includes:
- `run_id`
- `job_type`
- `project_id`
- `execution_status`
- `approval_state`
- `artifact_refs`

This allows operators to verify execution progress.

## 7. Approval Workflow

Some jobs require operator approval.

Example:
- `qs.po_generate`

When approval is required:
- `execution_status = blocked`
- `approval_state = pending`

Operators must approve before execution continues.

## 8. Inspecting Artifacts

Artifacts represent execution outputs.

Artifacts are stored under:

`runtime_root/artifacts/`

Example structure:

```text
runtime_root/artifacts/
   qs/
      run_20260309_001/
         boq_report.json
         cost_estimate.json
```

Artifacts must remain immutable.

Reference:
- `docs/0LUKA_ARTIFACT_MODEL.md`

## 9. Handling Failures

When a run fails, the runtime state will indicate:

`execution_status = FAILED`

Operators should inspect:
- run state
- artifact references
- system logs

Example investigation steps:
- check runtime state
- check artifact path
- check activity logs

## 10. Runtime Validator Issues

The runtime validator may detect violations.

Common issues:
- invalid state transition
- missing artifact
- approval bypass
- projection drift

Validator errors must be investigated immediately.

Reference:
- `docs/0LUKA_RUNTIME_VALIDATOR.md`

## 11. Guardian Recovery Actions

The runtime guardian automatically attempts recovery.

Typical actions:
- restart dispatcher
- rebuild projection
- mark run FAILED
- pause execution

Guardian events appear in:

`observability/activity_feed.jsonl`

Reference:
- `docs/0LUKA_RUNTIME_GUARDIAN.md`

## 12. Incident Handling

When system anomalies occur, operators should follow this process.

Step 1:
- identify the affected run.

Step 2:
- inspect runtime state.

Step 3:
- check artifact integrity.

Step 4:
- review activity logs.

Step 5:
- determine if recovery is required.

## 13. Log Inspection

Runtime events are recorded in:

`observability/activity_feed.jsonl`

Example event:

```json
{
  "event": "run_failed",
  "run_id": "run_20260309_002",
  "reason": "artifact_missing",
  "timestamp": "2026-03-09T04:00:00Z"
}
```

Logs allow operators to trace system behavior.

## 14. Projection Rebuild

If read models drift from runtime state:

projection rebuild

Example tool:

`tools/ops/rebuild_projection.py`

Projection rebuild restores Mission Control visibility.

## 15. Dispatcher Restart

If task execution stalls:

restart dispatcher

Example:

```bash
launchctl kickstart -k gui/$UID/com.0luka.dispatcher
```

Restarting dispatcher resumes task processing.

## 16. System Maintenance

Periodic maintenance tasks include:
- log rotation
- artifact storage checks
- runtime health review
- dependency updates

Maintenance should not interrupt active runs.

## 17. Safety Guidelines

Operators must follow strict safety practices.

Never modify runtime state manually:
- `runtime_root/state`

Never edit artifacts directly:
- artifacts must remain immutable.

Never bypass runtime execution:
- all jobs must pass through dispatcher.

## 18. Platform Recovery

If the system becomes unstable:
- pause dispatcher
- inspect runtime state
- restart guardian
- restart dispatcher

Recovery must preserve runtime integrity.

## 19. Operational Responsibilities

Operators are responsible for:
- runtime monitoring
- incident response
- system maintenance
- approval handling

Operators must ensure the system remains stable.

## 20. Reference Documentation

Operators should be familiar with:
- `docs/0LUKA_PLATFORM_MODEL.md`
- `docs/0LUKA_EXECUTION_MODEL.md`
- `docs/0LUKA_RUNTIME_OPERATIONS.md`
- `docs/0LUKA_RUNTIME_VALIDATOR.md`
- `docs/0LUKA_RUNTIME_GUARDIAN.md`

These documents define the platform architecture and operational procedures.

## Summary

The operator guide provides procedures for maintaining the 0luka runtime platform.

Operators are responsible for:
- monitoring system health
- handling approvals
- investigating failures
- maintaining runtime stability

By following this guide, operators can ensure the platform remains stable, auditable, and reliable.
