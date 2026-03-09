# QS v2 Execution Plan (Engineering Grade)

System: 0luka  
Component: QS (Quantity Surveying Engine)  
Baseline: `docs/review/QS_v1_VERIFIED.md`

## Objective

Advance QS from verified v1 slice to operational v2 engine with stronger scale behavior, domain depth, and operational controls, while preserving runtime stability and sealed boundaries.

## Scope Guard

In scope:
- QS application-layer enhancements
- deterministic handler depth
- artifact and projection reliability improvements
- volume and stability verification

Out of scope:
- runtime architecture redesign
- bridge protocol redesign
- approval semantic redesign
- watchdog/retry/dead-letter redesign

## 12 Tasks

1. `V2-T01` Schema Lock for Job Context  
Define strict per-job context schema for `boq_extract`, `cost_estimate`, `po_generate`, `report_generate` with fail-closed validation.

2. `V2-T02` Schema Lock for Job Outputs  
Define strict output contracts for each job, including canonical `artifact_refs` shape and job result metadata.

3. `V2-T03` BOQ Extractor v2 Adapter Layer  
Introduce bounded parser adapter interface (no heavy model logic) and normalized quantities output schema.

4. `V2-T04` Cost Estimate v2 Model  
Implement deterministic costing pipeline using snapshot-style price input contract and reproducible totals.

5. `V2-T05` PO Generator v2 Templates  
Implement deterministic PO document generation contract with stable artifact names and section schema.

6. `V2-T06` Report Generator v2 Composer  
Compose project report from BOQ + Cost + PO refs with deterministic ordering and section coverage.

7. `V2-T07` Artifact Integrity Checks  
Add content hash + existence checks for produced refs and enforce outbox/sidecar consistency assertions.

8. `V2-T08` Mission Control Projection Extensions  
Add non-breaking projection fields for job execution diagnostics and artifact integrity status.

9. `V2-T09` Unknown/Error Taxonomy  
Standardize job execution error codes and reasons so failures are diagnosable without log archaeology.

10. `V2-T10` Concurrency Safety Proof (10-run)  
Run a controlled 10-run mixed workload to verify deterministic state/artifact/projection consistency.

11. `V2-T11` Concurrency Safety Proof (50-run)  
Run 50-run mixed approval/state workload; verify no drift, no approval bypass, and stable projection snapshots.

12. `V2-T12` v2 Seal + Compatibility Report  
Produce final v2 verification artifact with compatibility matrix versus v1 frozen interfaces.

## Dependency Graph

- `V2-T01 -> V2-T02`
- `V2-T02 -> V2-T03`
- `V2-T02 -> V2-T04`
- `V2-T02 -> V2-T05`
- `V2-T02 -> V2-T06`
- `V2-T03 -> V2-T06`
- `V2-T04 -> V2-T05`
- `V2-T04 -> V2-T06`
- `V2-T05 -> V2-T06`
- `V2-T03 -> V2-T07`
- `V2-T04 -> V2-T07`
- `V2-T05 -> V2-T07`
- `V2-T06 -> V2-T07`
- `V2-T07 -> V2-T08`
- `V2-T07 -> V2-T09`
- `V2-T08 -> V2-T10`
- `V2-T09 -> V2-T10`
- `V2-T10 -> V2-T11`
- `V2-T11 -> V2-T12`

## Risk Guardrails

1. Preserve frozen v1 interfaces unless explicit major-version branch is opened.
2. Fail-closed on schema mismatch, unknown job type, or malformed artifact refs.
3. Keep approval-gate behavior unchanged; no execution before approval for approval-required jobs.
4. Keep runtime sidecar as authoritative truth source; do not add parallel mutable stores.
5. Keep Mission Control read-only; no write-side effects in projection paths.
6. Prevent artifact drift by verifying sidecar/outbox/projection equality in tests.
7. Block rollout if any concurrency proof shows state divergence.
8. Isolate transport-layer issues from domain-layer acceptance decisions.

## Acceptance Gates

Gate A (after `V2-T04`):
- deterministic cost outputs for same input snapshot
- contract tests green

Gate B (after `V2-T07`):
- artifact integrity checks green
- no sidecar/outbox mismatch

Gate C (after `V2-T11`):
- 50-run mixed proof green
- no approval bypass
- no projection drift

Gate D (final `V2-T12`):
- compatibility report approved
- v2 milestone sealed

## Deliverables

- `QS_v2_SCHEMA_LOCK.md` (T01-T02)
- `QS_v2_HANDLER_SPEC.md` (T03-T06)
- `QS_v2_INTEGRITY_REPORT.md` (T07-T09)
- `QS_v2_VOLUME_PROOF.md` (T10-T11)
- `QS_v2_VERIFIED.md` (T12)

## Execution Order (Recommended)

1. T01-T02
2. T03-T06
3. T07-T09
4. T10-T11
5. T12

