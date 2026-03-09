# QS Product Slice v1 — Verified Milestone

System: 0luka  
Component: QS (Quantity Surveying Engine)  
Date: 2026-03-09  
Status: VERIFIED

## 1) Executive Summary

QS Product Slice v1 is verified on the live 0luka runtime path.

Verified end-to-end:
- live ingress submission
- dispatcher consumption
- runtime sidecar state persistence
- approval-gated execution for `qs.po_generate`
- registered job execution via QS job registry
- artifact linkage and reproducibility
- Mission Control read-model projection consistency
- fail-closed behavior for unknown jobs

No core runtime redesign was introduced.

## 2) Runtime Path

Ingress  
-> Router  
-> Runtime sidecar state  
-> Approval gate  
-> `run_registered_job(job_type, context)`  
-> Artifact persistence  
-> Outbox projection  
-> Mission Control read-model

Execution context passed to registry:

```json
{
  "run_id": "...",
  "job_type": "...",
  "project_id": "..."
}
```

## 3) Runs Verified

| Run ID | Job Type | Approval | Result |
|---|---|---|---|
| `qs_v1_20260309_092628_boq` | `qs.boq_extract` | not required | completed |
| `qs_v1_20260309_092628_cost` | `qs.cost_estimate` | not required | completed |
| `qs_v1_20260309_092628_po` | `qs.po_generate` | required | completed after approval |
| `qs_v1_20260309_092628_report` | `qs.report_generate` | not required | completed |
| `qs_v1_20260309_092628_unknown` | `qs.unknown_job` | n/a | fail-closed |

## 4) Approval-Gated Proof (`qs.po_generate`)

Dedicated transition proof run:
- `qs_v1_20260309_094251_po_transition`

Before approval:
- `approval_state=pending_approval`
- `execution_status=blocked`
- `job_execution_state=not_started`
- `artifacts=[]`

After approval:
- `approval_state=approved`
- `execution_status=allowed`
- `job_execution_state=completed`
- PO artifact reference persisted

Proof artifact:
- `/tmp/qs_v1_po_transition.json`

## 5) Artifact Truth Path

Artifact refs were checked across three sources:
1. runtime sidecar: `/Users/icmini/0luka_runtime/state/qs_runs/<run_id>.json`
2. outbox projection: `/Users/icmini/0luka/interface/outbox/tasks/<run_id>.result.json`
3. Mission Control read-model: `GET /api/qs_runs/<run_id>`

Result:
- successful runs matched across all 3 sources
- unknown job had no fabricated artifacts (`[]`)

Proof artifact:
- `/tmp/qs_v1_proof_report.json`

## 6) Fail-Closed Verification

Unknown job type:
- `qs.unknown_job`

Observed:
- dispatcher result: rejected
- runtime sidecar:
  - `runtime_state=failed`
  - `execution_status=failed`
  - `job_execution_state=failed`
- no artifact fabrication

## 7) Boundaries Preserved

Unchanged in this milestone:
- bridge payload schema
- dispatcher/router architecture
- approval semantics
- Mission Control semantics
- artifact truth path ownership
- watchdog/retry/dead-letter/proof pipeline

## 8) Known Notes

- Domain flow is verified.
- Mission Control HTTP transport bug on `:7010` was fixed separately in `MC-HTTP-01` (route signature mismatch).

## 9) Final Statement

QS Product Slice v1 is verified on the live 0luka runtime path.

QS is now a verified product slice (not only a contract prototype), with live execution, approval gating, deterministic artifacts, and operator visibility.

## Frozen Interfaces

The following interfaces are considered stable for QS v1:

- `run_registered_job(job_type, context)`
- `artifact_refs` return contract
- runtime sidecar state format
- Mission Control QS projection schema

Future changes must remain backward-compatible unless a new QS major version is introduced.
