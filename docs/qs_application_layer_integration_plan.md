# 1. APPLICATION ROLE

`qs` is a **domain application layer** that executes QS/BOQ/compliance/PO workflows on top of the existing 0luka runtime. It owns business semantics: estimating rules, quantity logic, factor calculations, compliance assertions, PO drafting, and output packaging per project run. It should be versioned and evolved like a product module, with explicit input/output contracts, deterministic processing steps, and reviewable artifacts.

`qs` is **not** a control-plane subsystem. It must not become a scheduler, runtime supervisor, approval engine, self-healing daemon, or policy authority. Those are sealed 0luka concerns. `qs` submits work, responds to gate outcomes, emits domain events/results, and surfaces operator-facing status through interfaces that 0luka already governs.

Why app layer placement is correct:
- Domain volatility is high (estimating rules, compliance interpretations, PO formats) and should be isolated from kernel stability requirements.
- Governance sensitivity is high (publish/overwrite/PO actions), so domain actions should call into existing 0luka policy/approval gates instead of embedding parallel controls.
- Auditability is preserved when `qs` behaves as a transparent client of 0luka queue/history systems, not as a hidden orchestration system.
- Deterministic, replayable job execution is easier when runtime concerns are centralized in 0luka and business logic stays in `qs` handlers.

# 2. APP ARCHITECTURE

## A) Domain layer (pure business logic)
- `calc`: BOQ/quantity takeoff and estimate computation from structured inputs.
- `factor_f`: deterministic adjustment/recalculation against approved factor sets.
- `compliance`: rule-pack checks and exception classification.
- `po`: PO draft generation from approved estimate/compliance context.
- `artifact`: render JSON/CSV/PDF/report bundles and review snapshots.

Constraints:
- No direct runtime supervision logic.
- Pure functions where possible + deterministic side effects behind interfaces.

## B) Integration layer (contracts to 0luka)
- Queue adapter: submit `qs` jobs to remediation/supervised queues.
- Approval adapter: request and consume approval decisions for gated actions.
- Policy adapter: ask autonomy policy for allow/deny/needs-approval decisions.
- Runtime status adapter: receive worker/job lifecycle callbacks.
- Audit/history adapter: append domain event trail and artifact references.

Contracts:
- Canonical job envelope (`job_type`, `lane`, `idempotency_key`, `inputs_ref`, `requested_by`, `trace_id`).
- Canonical terminal states (`succeeded`, `failed_deterministic`, `failed_transient`, `rejected_policy`, `awaiting_approval`, `cancelled`).
- Artifact metadata contract (`artifact_id`, `hash`, `schema_version`, `review_status`).

## C) Operator layer (thin API + Mission Control projection)
- `qs` API endpoints for create-run, get-run, list-runs, fetch-artifacts, request-rerun.
- Read models for Mission Control: queue depth, active runs, approvals pending, failed runs, latest artifacts.
- No separate heavyweight ops UI required initially; Mission Control remains primary surface.

# 3. DOMAIN MODULES

## `calc_engine`
- Purpose: produce BOQ/estimate baseline from project inputs.
- Inputs: project scope, measurement inputs, pricing tables, assumptions version.
- Outputs: line-item quantities, totals, calculation trace.
- Failure mode: invalid/insufficient inputs => deterministic fail; missing reference data => transient fail.
- Approval required: not for draft run; yes if publishing final estimate.

## `factor_f`
- Purpose: apply approved factor F transformations to baseline.
- Inputs: baseline estimate artifact, factor set/version, lane context.
- Outputs: adjusted estimate + delta report.
- Failure mode: unsupported factor version => deterministic fail.
- Approval required: yes if factor change alters already published outputs.

## `compliance`
- Purpose: run compliance rule checks and emit pass/fail/exception set.
- Inputs: estimate artifact, jurisdiction/rule pack version, project metadata.
- Outputs: compliance report + exception list.
- Failure mode: rule-pack unavailable => transient fail; malformed data => deterministic fail.
- Approval required: required to accept compliance exceptions.

## `po_writer`
- Purpose: generate PO draft from approved estimate/compliance context.
- Inputs: approved estimate ID, vendor/profile data, terms template.
- Outputs: PO draft artifact + structured PO payload.
- Failure mode: missing vendor terms => deterministic fail.
- Approval required: yes before PO finalization/dispatch.

## `project_run`
- Purpose: orchestrate deterministic sequence across calc/factor/compliance/PO.
- Inputs: run config, selected modules, assumption bundle.
- Outputs: run manifest, stage statuses, artifact index.
- Failure mode: stage fail halts downstream writes (fail closed on critical actions).
- Approval required: depends on stage action; enforced per gated transition.

## `artifact_export`
- Purpose: generate operator/shareable outputs (JSON/CSV/PDF bundles).
- Inputs: run manifest, module outputs, export profile.
- Outputs: immutable artifact set + hashes.
- Failure mode: renderer crash => transient fail.
- Approval required: needed when overwriting a designated “final” artifact.

## `input_validation`
- Purpose: schema and business-rule validation before queue submission.
- Inputs: API payloads + referenced objects.
- Outputs: normalized payload or validation errors.
- Failure mode: deterministic reject with actionable error set.
- Approval required: no.

# 4. 0LUKA INTEGRATION POINTS

`qs` must integrate with these existing 0luka surfaces:
- **Remediation queue**: all write-capable or long-running jobs dispatched via supervised queues.
- **Approval system**: explicit approval requests for gated actions (PO finalize, publish, overwrite, exception acceptance).
- **Autonomy policy**: pre-flight policy check for each critical transition (`allow`, `deny`, `needs_approval`).
- **Mission Control**: publish run/job status projections and approval-needed signals.
- **History/audit logs**: append immutable event records + artifact references + decision provenance.
- **Worker supervision**: rely on 0luka worker lifecycle, retries, and self-healing; no custom internal daemon in `qs`.

What `qs` must NOT own:
- Scheduler semantics, worker healing logic, approval decision storage authority, global policy engine, control-plane alert routing.

# 5. JOB / QUEUE MODEL

Minimal deterministic envelope:
- `job_id`, `job_type`, `lane`, `requested_by`, `trace_id`, `idempotency_key`
- `input_schema_version`, `inputs_ref`, `created_at`
- `gating_required[]`, `policy_decision`, `approval_ticket?`

State machine:
- `queued -> running -> (succeeded | failed_transient | failed_deterministic | rejected_policy | awaiting_approval | cancelled)`
- `awaiting_approval -> queued` on approval; `awaiting_approval -> cancelled` on reject/timeout.

## `boq_generate`
- Input schema sketch: `{project_id, scope_ref, measurement_ref, pricing_table_ref, assumptions_ref}`
- Output artifact: `boq.json`, `calc_trace.json`, `summary.csv`
- Retry: yes for transient reference fetch failures.
- Queue suitability: high (CPU + deterministic).

## `factor_f_recalc`
- Input: `{base_artifact_id, factor_version, lane, reason}`
- Output: `estimate_adjusted.json`, `delta_report.json`
- Retry: yes for transient artifact fetch; no for unsupported factor.
- Queue suitability: high.

## `compliance_check`
- Input: `{estimate_artifact_id, jurisdiction, rulepack_version, project_meta}`
- Output: `compliance_report.json`, `exceptions.json`
- Retry: yes for rulepack fetch; no for invalid schema.
- Queue suitability: high.

## `po_generate`
- Input: `{approved_estimate_id, vendor_id, terms_template_id, lane}`
- Output: `po_draft.json`, `po_render.pdf`
- Retry: limited; requires approval before final state transitions.
- Queue suitability: high with gating hooks.

## `report_export`
- Input: `{run_id, export_profile, artifact_ids[]}`
- Output: report bundle (`zip` + manifest/hash)
- Retry: yes for renderer/transient IO issues.
- Queue suitability: high.

# 6. APPROVAL / POLICY MODEL

Policy-first, approval-second flow for critical actions:
1. `qs` asks autonomy policy for decision.
2. If `allow`, continue.
3. If `needs_approval`, create approval ticket and pause job (`awaiting_approval`).
4. If `deny`, terminate with `rejected_policy`.

Minimum gated actions:
- PO generation finalization/dispatch.
- Overwrite of a designated final output artifact.
- Publish estimate as official/baseline.
- Accept compliance exception.
- Rerun using changed assumptions when a prior result is already published.

Lane-scoped mapping (example):
- `lane.qs.estimate.publish`
- `lane.qs.po.finalize`
- `lane.qs.compliance.exception.accept`
- `lane.qs.artifact.overwrite_final`
- `lane.qs.run.rerun_changed_assumptions`

Fail-closed rule:
- Any missing policy response, stale approval ticket, or ambiguous state => block write action and mark run as needing operator intervention.

# 7. OPERATOR UX

Mission Control should expose a thin `qs` panel with:
- Job queue view (`queued/running/awaiting_approval/failed`).
- Active worker + current stage for each run.
- Latest output artifact set with hashes and schema version.
- Failed runs with deterministic vs transient classification.
- Approval-required cards with lane/action context.
- Remediation events linked to affected run/job.

Initial UX should prioritize triage and governance visibility over rich editing.

# 8. FILE / MODULE PLAN

Suggested `qs` app-layer layout:

- `apps/qs/domain/`
  - `calc_engine.py`
  - `factor_f.py`
  - `compliance.py`
  - `po_writer.py`
  - `artifact_export.py`
  - `input_validation.py`
- `apps/qs/integration/`
  - `queue_adapter.py`
  - `policy_adapter.py`
  - `approval_adapter.py`
  - `audit_adapter.py`
  - `mission_control_projection.py`
- `apps/qs/orchestration/`
  - `project_run_service.py`
  - `job_handlers.py`
  - `state_machine.py`
- `apps/qs/api/`
  - `routes_runs.py`
  - `routes_artifacts.py`
  - `schemas.py`
- `apps/qs/tests/`
  - `test_domain_calc_engine.py`
  - `test_job_state_machine.py`
  - `test_policy_approval_gates.py`
  - `test_artifact_audit_chain.py`

Design intent:
- Domain isolated from infrastructure.
- Integration adapters as single boundary to 0luka.
- Explicit orchestration state machine with deterministic transitions.

# 9. IMPLEMENTATION PHASES

## Phase A — App contracts + job schemas
- Scope: define job envelope, state machine, artifact metadata schemas, input validation contracts.
- Why: creates stable integration surface before implementation detail.
- Dependency: none.
- Stop condition: schema docs + contract tests passing.

## Phase B — Queue integration
- Scope: implement queue adapter + handlers for `boq_generate`, `factor_f_recalc`, `compliance_check`, `report_export`.
- Why: enables supervised deterministic execution on 0luka runtime.
- Dependency: Phase A contracts.
- Stop condition: end-to-end queued runs with deterministic terminal states.

## Phase C — Approval-gated critical actions
- Scope: integrate policy/approval adapters for publish/overwrite/PO/compliance-exception/rerun-changed-assumptions.
- Why: enforce fail-closed governance.
- Dependency: Phases A-B.
- Stop condition: gated actions cannot complete without allow/approval; audit trail records decisions.

## Phase D — Mission Control visibility
- Scope: mission-control projection feed and run/job read models.
- Why: operators need real-time observability and intervention context.
- Dependency: Phases B-C.
- Stop condition: Mission Control displays queue, failures, approvals, remediation linkage for `qs` jobs.

## Phase E — Artifact/report outputs hardening
- Scope: finalize export profiles, immutable artifact hashes, reproducibility checks.
- Why: reviewability and audit integrity for business outputs.
- Dependency: Phases B-C (and D for operator consumption).
- Stop condition: reproducible exports with hash + provenance chain verified in tests.

# 10. RISKS / BOUNDARIES

Must stay in 0luka:
- Runtime supervision, retries policy authority, self-healing controls, global policy/approval authority, operator control-plane integrity.

Must stay in `qs`:
- Business rules, BOQ math, factor logic, compliance interpretation, PO domain templates, report semantics.

Do not couple:
- `qs` domain code directly to worker internals.
- Approval decisions to ad-hoc local flags.
- Artifact truth to mutable in-place files without immutable IDs/hashes.

Do not over-automate yet:
- Free-form AI decisioning for compliance/PO approvals.
- Autonomous publish/finalize without deterministic rule + approval path.

# 11. DEFINITION OF DONE

`qs` is a real 0luka application layer when all are true:
- All key workflows run as queued supervised jobs through 0luka interfaces.
- Critical write actions are policy/approval-gated and fail closed.
- Domain outputs are deterministic, versioned, and reproducible.
- Every run produces an audit-linked artifact chain and decision provenance.
- Mission Control can show live `qs` run state, pending approvals, failures, and remediation linkage.
- `qs` contains no duplicated runtime/governance mechanisms.

# 12. FIRST EXECUTION STEP

Create and commit an **Application Contract Pack** for `qs` containing:
- job envelope schema,
- terminal state machine spec,
- gating action matrix (policy + approval),
- artifact metadata/audit linkage schema,
- minimal contract tests.

This is the smallest high-value step because it locks the boundary between `qs` and sealed 0luka before implementation begins.
