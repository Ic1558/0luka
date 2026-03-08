# 1. APPLICATION ROLE

`qs` is the business/domain application layer that turns project inputs (drawings, specs, assumptions, rates) into quantity takeoff, BOQ/estimate, factor-F adjusted outputs, compliance assessments, PO drafts, and final project artifacts.

`qs` is **not** runtime, governance, queue supervision, approval orchestration, remediation ownership, or control-plane health logic. Those remain in sealed 0luka.

Why `qs` belongs above 0luka:
- Domain logic changes frequently (rules, rates, templates, standards) and should evolve independently.
- Runtime/governance must remain stable and sealed.
- Explicit interfaces keep auditability, isolation, and rollback safety.

---

# 2. APP ARCHITECTURE

## A) Domain Layer (`qs.domain.*`)
Pure deterministic business logic; no direct infrastructure calls.

- Parsers/validators for project assumptions and input references
- Quantity and cost calculation services
- Factor F computation service
- Compliance rule evaluation
- PO draft generation
- Artifact/report rendering

## B) 0luka Integration Layer (`qs.adapters.zeroluka.*`)
Thin adapters that call sealed platform interfaces.

- Job intake / status update adapter (queue integration)
- Approval-request adapter
- Policy-context reader (effective autonomy lane, presets, expiry)
- Mission Control event publisher
- Remediation signal reader
- Health/alert emitter hooks

## C) Operator-Facing Layer (`qs.api.*`, `qs.views.*`)
App-specific APIs/views for operators; no runtime control decisions.

- Endpoints for submit/run/status/results
- Projection views for job timeline, approval status, output bundle
- Read-only surfacing of remediation and retry lineage from 0luka

---

# 3. DOMAIN MODULES

| Module | Purpose | Inputs | Outputs | Failure Mode | Approval Required |
|---|---|---|---|---|---|
| `input_validation` | Normalize and validate job payloads | project refs, assumptions, rates, versions | validated input envelope + deterministic hash | reject with validation errors; no partial write | No |
| `calc_engine` | Quantity takeoff + BOQ + estimate | validated geometry/spec quantities, rate cards | BOQ lines, estimate totals, calc trace | deterministic fail with trace code; retry after input fix | No |
| `factor_f` | Apply factor-F policy to estimates | estimate snapshot, risk/context params | factor-F adjusted totals + reasoning trace | fail closed if missing factor policy version | No |
| `compliance` | Evaluate compliance rules | boq/estimate/factor-F outputs + rule pack | pass/fail findings, exception candidates | explicit non-compliance findings artifact | No (check itself), Yes for accepting exception |
| `po_writer` | Generate PO draft set | approved supplier map, approved estimate lines | PO draft artifacts (structured + PDF) | hard fail on missing mandatory supplier fields | Yes (critical write) |
| `project_run` | Aggregate deterministic run graph | run config + job references | run manifest, stage status, lineage | stage-level terminal error with resumable markers | Depends on stage |
| `artifact_export` | Build reports/bundles | run manifest + stage outputs | immutable artifact bundle, checksums | fail without mutating published outputs | Yes if overwrite/destructive |
| `output_publish` | Publish final outputs to operator channel | approved final artifacts + destination | published output record + publish receipt | fail safe with no publish on partial writes | Yes (publish estimate/final output) |

---

# 4. 0LUKA INTEGRATION POINTS

`qs` consumes from 0luka (explicit interfaces only):

1. Queue API
   - Enqueue deterministic job types
   - Receive dispatch callbacks / state updates
2. Approval API
   - Create approval intents for gated actions
   - Poll/subscribe decision status, expiry, drift
3. Policy API
   - Read effective autonomy lane and action allowances
4. Mission Control visibility hooks
   - Emit structured job/run events for operator timeline
5. Remediation history API
   - Read retry/remediation lineage; tag outputs accordingly
6. Worker supervision contract
   - Accept worker-assigned execution context (no worker lifecycle ownership)
7. Health/alert hooks
   - Emit app health signals and domain error rates

`qs` must **not** own:
- queue scheduler/supervisor
- approval engine semantics
- policy conflict resolution
- remediation orchestration
- global observability core
- runtime/process management

---

# 5. JOB / QUEUE MODEL

Common job envelope:
- `job_id`, `job_type`, `project_id`, `run_id`, `input_ref`, `input_hash`, `policy_snapshot_id`, `requested_by`, `created_at`

Common states:
`queued -> running -> awaiting_approval (optional) -> completed | failed | cancelled | expired`

## `boq_generate`
- Input schema sketch: `{project_scope_ref, drawing_refs[], assumptions, rate_card_id, calc_version}`
- Output artifact sketch: `boq.json`, `estimate.json`, `calc_trace.json`
- Retry suitability: Yes (idempotent by `input_hash`)
- Approval: No

## `factor_f_recalc`
- Input schema sketch: `{estimate_ref, factor_policy_version, context:{risk_class, schedule_pressure}}`
- Output artifact sketch: `factor_f_result.json`, `adjusted_estimate.json`
- Retry suitability: Yes (idempotent)
- Approval: No (unless marked as publish overwrite)

## `compliance_check`
- Input schema sketch: `{boq_ref, estimate_ref, rule_pack_version, jurisdiction}`
- Output artifact sketch: `compliance_report.json`, `exceptions.json`
- Retry suitability: Yes
- Approval: No for check; Yes for exception acceptance action

## `po_generate`
- Input schema sketch: `{approved_estimate_ref, supplier_catalog_ref, terms_template_id}`
- Output artifact sketch: `po_drafts.json`, `po_bundle.pdf`
- Retry suitability: Conditional (idempotent key includes supplier snapshot)
- Approval: Yes (before final PO artifact issuance)

## `report_export`
- Input schema sketch: `{run_manifest_ref, export_profile, destination, overwrite_mode}`
- Output artifact sketch: `run_report.pdf`, `artifact_manifest.json`, `checksums.txt`
- Retry suitability: Yes if non-destructive; guarded if overwrite
- Approval: Yes when overwrite/destructive/finalized output target

---

# 6. APPROVAL / POLICY MODEL

Gated `qs` actions (minimum):

1. PO generation finalization
2. Overwrite final output
3. Publish estimate
4. Accept compliance exception
5. Rerun with changed assumptions affecting approved outputs
6. Final report export when destructive/overwriting

Lane mapping (example):
- **Lane A (auto-allowed)**: read-only checks, non-destructive recalcs, draft artifacts
- **Lane B (operator approval required)**: publish estimate, accept compliance exception, changed-assumption rerun after prior approval
- **Lane C (strict approval + expiry)**: PO finalization, destructive overwrite/export to final destination

Policy binding rules:
- Every gated request includes `policy_snapshot_id` and `approval_intent_id`.
- If policy drifts or approval expires before execution, job returns `expired` and requires re-approval.
- Audit record must persist intent, approver, decision timestamp, and executed artifact checksum.

---

# 7. OPERATOR UX

Mission Control should show a thin `qs` projection:

- Queued jobs: job type, project, submitter, age
- Running jobs: stage progress + current module
- Failed jobs: deterministic error code, failure artifact link, suggested remediation path from 0luka
- Approval-required jobs: action label, lane, expiry timer, policy snapshot
- Latest outputs: per project/run (boq, estimate, compliance, po, report)
- Remediation/retries: lineage chain (`original -> retried -> recovered`) and whether output is superseded

No custom runtime consoles inside `qs`; only domain-centric projections.

---

# 8. FILE / MODULE PLAN

Proposed `repos/qs` layout (application repo evolution target):

```text
repos/qs/
  qs/
    domain/
      input_validation.py
      calc_engine.py
      factor_f.py
      compliance.py
      po_writer.py
      artifact_export.py
      output_publish.py
      project_run.py
    schemas/
      job_envelope_v1.json
      boq_generate_v1.json
      factor_f_recalc_v1.json
      compliance_check_v1.json
      po_generate_v1.json
      report_export_v1.json
    adapters/
      zeroluka_queue.py
      zeroluka_approval.py
      zeroluka_policy.py
      zeroluka_mission_control.py
      zeroluka_remediation.py
      zeroluka_health.py
    api/
      routes_jobs.py
      routes_outputs.py
    services/
      orchestrate_run.py
      idempotency.py
      artifact_registry.py
  artifacts/
    templates/
      boq_template.md
      compliance_template.md
      po_template.md
      run_report_template.md
  tests/
    domain/
    adapters/
    api/
    integration/
      test_qs_zeroluka_contracts.py
  docs/
    qs_application_layer_contract.md
```

Boundary rule: `domain/` cannot import `adapters/`.

---

# 9. IMPLEMENTATION PHASES

## Phase 1 — Contract lock for integration boundaries
- Scope: define job envelopes, approval intent payloads, event schema, idempotency key format
- Why: prevents scope leakage into 0luka internals
- Dependency: existing sealed 0luka API contracts
- Stop condition: schema files versioned + contract tests passing

## Phase 2 — Deterministic domain core (BOQ + factor F + compliance)
- Scope: implement `input_validation`, `calc_engine`, `factor_f`, `compliance` with pure-function traces
- Why: core business value with auditable determinism
- Dependency: phase 1 schemas
- Stop condition: golden tests produce stable checksums for fixed fixtures

## Phase 3 — Gated critical actions (PO + publish + overwrite)
- Scope: `po_writer`, `output_publish`, approval adapter wiring for gated transitions
- Why: enforce safety for irreversible business outputs
- Dependency: phases 1-2 + approval contracts
- Stop condition: unauthorized paths blocked; approval path audited end-to-end

## Phase 4 — Operator projection + run orchestration
- Scope: Mission Control projection endpoints, run timeline, remediation lineage display
- Why: operational usability without duplicating runtime control
- Dependency: phases 1-3 + Mission Control event adapter
- Stop condition: operators can track queued/running/failed/approval/outputs in one view

## Phase 5 — Hardening and release readiness
- Scope: idempotency, retry policy tuning, drift/expiry handling, failure playbooks
- Why: production resilience with deterministic recovery behavior
- Dependency: full functional slice
- Stop condition: reliability SLO tests and audit completeness checks pass

---

# 10. RISKS / BOUNDARIES

What belongs in `qs`:
- domain calculations and artifacts
- domain rule packs and templates
- app-level APIs/projections

What stays in 0luka:
- job scheduling/supervision
- approval engine and governance history
- remediation orchestration and self-healing control
- control-plane health/state authority

Dangerous coupling points:
- embedding approval decision logic inside `qs`
- relying on internal queue worker implementation details instead of contracts
- writing directly to Mission Control storage bypassing published hooks

Do not automate too early:
- auto-accept compliance exceptions
- auto-finalize POs
- destructive overwrites without explicit gate and expiry checks

---

# 11. DEFINITION OF DONE

`qs` is a real app layer on top of 0luka when all are true:

1. All target job types run through 0luka queue contracts only.
2. Critical write actions are blocked unless valid approval intent is present and unexpired.
3. Deterministic domain modules produce traceable artifacts with stable hashes for identical inputs.
4. Mission Control shows `qs` job lifecycle, approvals, failures, retries, and latest outputs.
5. Audit trail links each final artifact to job input hash, policy snapshot, approval decision, and checksum.
6. `qs` repository/module boundaries enforce domain vs adapter separation.
7. Recovery/remediation events from 0luka are visible in `qs` output lineage without `qs` owning remediation logic.

---

# 12. FIRST EXECUTION STEP

Create and commit **Phase 1 contract package** in the `qs` repo (`job_envelope_v1`, five job payload schemas, approval intent schema, and one integration contract test file) so implementation can start with fixed boundaries and no leakage into 0luka internals.
