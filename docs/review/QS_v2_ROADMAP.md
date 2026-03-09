# QS v2 Roadmap — From Verified Slice to Operational Engine

System: 0luka  
Component: QS (Quantity Surveying Engine)  
Baseline: `docs/review/QS_v1_VERIFIED.md`

## Objective

Move from verified product slice to operational QS engine without breaking sealed runtime boundaries.

## Track A — Scale and Stability

Goal: prove operational behavior under load.

Phase A1:
- run 10-50 mixed QS jobs (`boq_extract`, `cost_estimate`, `po_generate`, `report_generate`)
- verify sidecar/outbox/Mission Control consistency under concurrency
- verify no artifact drift across repeated reads

Phase A2:
- add stress evidence pack:
  - run latency summary
  - commit/reject ratios
  - artifact path integrity checks
- define threshold-based acceptance criteria

DoD:
- no state divergence across truth surfaces
- fail-closed semantics preserved under load
- no approval bypass under concurrency

## Track B — Business Logic Depth

Goal: upgrade skeleton handlers into domain-meaningful jobs.

Phase B1 (`qs.boq_extract`):
- real BOQ parsing adapters (bounded)
- normalized quantity table schema lock

Phase B2 (`qs.cost_estimate`):
- deterministic cost model
- price source contract (`price_source_id`, versioned snapshot)

Phase B3 (`qs.po_generate`):
- PO template rendering contract
- deterministic PO artifact structure (md/pdf package)

Phase B4 (`qs.report_generate`):
- project report composition from BOQ + cost + PO refs
- final report schema and artifact naming lock

DoD:
- each handler produces reproducible outputs for same inputs
- artifacts stay under canonical truth path
- no new runtime ownership drift into QS layer

## Track C — Operational Readiness

Goal: make QS maintainable in production operations.

Phase C1:
- job-level observability fields in runtime sidecar
- execution error taxonomy (bounded codes)

Phase C2:
- runbook hardening for operator actions
- incident triage matrix for reject/fail cases

Phase C3:
- formal versioning for:
  - job registry interface
  - artifact ref schema
  - read-model payload compatibility

DoD:
- operators can diagnose failures without code dive
- backward compatibility policy documented for API/read-model

## Guardrails (Non-Negotiable)

- no bridge protocol redesign in QS v2 scope
- no dispatcher architecture rewrite in QS v2 scope
- no approval semantic redesign in QS v2 scope
- no proof/retry/watchdog scope creep in QS v2 scope
- maintain fail-closed behavior on unknown or malformed job execution

## Recommended Next Step

Start with Track A, Phase A1 (10-50 real-run volume proof), then lock findings into a `QS_v2_A1_REPORT.md` artifact before deepening business logic.

