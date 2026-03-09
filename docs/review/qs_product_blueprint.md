1. PRODUCT ROLE
`qs` is the first real product/application layer on top of 0luka. Its role is to turn project inputs into deterministic QS outputs: BOQ generation, compliance checking, PO preparation, and report export. It is not a runtime, not a dispatcher, not an approval engine, not a remediation system, and not a health supervisor. Those remain in sealed 0luka. `qs` is the correct first product layer because the repository already contains a dedicated QS module surface in [repos/qs/src/universal_qs_engine/cli.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/cli.py), domain data contracts in [repos/qs/src/universal_qs_engine/contracts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/contracts.py), artifact export logic in [repos/qs/src/universal_qs_engine/artifacts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/artifacts.py), and explicit job contracts in [repos/qs/src/universal_qs_engine/job_contracts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/job_contracts.py).

2. PRODUCT SCOPE
Initial production scope is four job types:
- `qs.boq_generate`
- `qs.compliance_check`
- `qs.po_generate`
- `qs.report_export`

In scope:
- project-level BOQ generation
- compliance evaluation and exception surfacing
- approval-gated PO generation
- export of operator-consumable reports and artifact bundles

Out of scope:
- runtime ownership
- remediation ownership
- health monitoring ownership
- dispatch ownership
- replacing 0luka approval semantics
- free-form AI estimating not backed by deterministic contracts

3. DOMAIN BLUEPRINT
`input_validation`
Purpose: normalize and validate incoming QS job payloads.
Inputs: project references, job parameters, artifact references.
Outputs: validated payload or fail-closed errors.
Side effects: none.
Failure modes: missing project reference, malformed payload, unsupported export mode.

`calc_engine`
Purpose: produce deterministic quantity and BOQ outputs.
Inputs: project scope, measurement inputs, pricing references, assumptions.
Outputs: BOQ lines, calculation trace, estimate totals.
Side effects: none by itself.
Failure modes: invalid inputs, missing pricing reference, inconsistent assumptions.

`compliance`
Purpose: evaluate project outputs against rule packs and acceptance conditions.
Inputs: BOQ or estimate artifacts, rule versions, project metadata.
Outputs: compliance report, exception candidates, gate summary.
Side effects: none by itself.
Failure modes: missing rule pack, malformed source artifact, non-compliant result.

`po_writer`
Purpose: build PO draft artifacts from approved estimate context.
Inputs: approved estimate references, vendor/profile data, terms template.
Outputs: PO draft payload and rendered export set.
Side effects: artifact generation.
Failure modes: missing vendor data, missing approved estimate context, blocked approval state.

`artifact_export`
Purpose: render and store JSON/XLSX/report outputs.
Inputs: computed QS outputs, workbook templates, output mode.
Outputs: export bundle and output URLs.
Side effects: filesystem writes under QS outputs.
Failure modes: export collision, renderer failure, incomplete inputs.

`project_run`
Purpose: represent a deterministic project run across the selected QS job.
Inputs: `project_id`, job type, references, assumptions snapshot.
Outputs: run status, artifact index, manifest-level summary.
Side effects: status and artifact references.
Failure modes: project not found, inconsistent run inputs, blocked downstream stage.

4. JOB MODEL
`qs.boq_generate`
- `job_type`: `qs.boq_generate`
- `inputs`: `project_id`, `source_refs`, `config_snapshot`, `output_mode`
- `expected_outputs`: `boq_json`, `internal_trace_xlsx`, `run_manifest`
- `requires_approval`: `false` by default
- `allowed_states`: `submitted`, `queued`, `running`, `blocked_approval`, `completed`, `failed`, `rejected`

`qs.compliance_check`
- `job_type`: `qs.compliance_check`
- `inputs`: `project_id`, `run_ref`, `acceptance_snapshot`, `review_queue`
- `expected_outputs`: `compliance_report_json`, `gate_summary`, `run_manifest`
- `requires_approval`: `false`
- `allowed_states`: `submitted`, `queued`, `running`, `blocked_approval`, `completed`, `failed`, `rejected`

`qs.po_generate`
- `job_type`: `qs.po_generate`
- `inputs`: `project_id`, `estimate_ref`, `package_scope`, `vendor_context`
- `expected_outputs`: `po_package`, `po_manifest`, `run_manifest`
- `requires_approval`: `true`
- `allowed_states`: `submitted`, `queued`, `running`, `blocked_approval`, `completed`, `failed`, `rejected`

`qs.report_export`
- `job_type`: `qs.report_export`
- `inputs`: `project_id`, `run_ref`, `report_type`, `delivery_format`
- `expected_outputs`: `summary_report`, `export_bundle`, `run_manifest`
- `requires_approval`: `false` by default
- `allowed_states`: `submitted`, `queued`, `running`, `blocked_approval`, `completed`, `failed`, `rejected`

These contracts are grounded in [repos/qs/src/universal_qs_engine/job_contracts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/job_contracts.py).

5. APPROVAL MODEL
Approval stays in 0luka. `qs` only declares which actions are gated and must respond to the result.

Minimum gated actions:
- `qs.po_generate`
- final owner-facing publish implied by BOQ/export flows
- overwrite of finalized output targets
- acceptance of compliance exceptions
- rerun with changed assumptions after prior approved output exists

Rules:
- `qs.po_generate` requires approval unconditionally in the current contract set.
- other jobs default to non-destructive behavior unless they move into publish/finalize semantics.
- if approval state is missing or ambiguous, `qs` must remain blocked rather than proceed.

6. ARTIFACT MODEL
Artifacts produced by `qs` must stay domain-specific while 0luka remains the platform for audit and control.

Core artifacts:
- BOQ JSON
- calculation trace / internal trace workbook
- compliance report
- PO package
- report export bundle
- run manifest

Grounding in current code:
- export bundle logic already exists in [repos/qs/src/universal_qs_engine/artifacts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/artifacts.py)
- current QS CLI already distinguishes internal trace export and blocked owner export behavior in [repos/qs/src/universal_qs_engine/cli.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/cli.py)

Artifact rules:
- draft/internal outputs can be generated without treating them as final publish
- final/published outputs must not bypass approval
- artifacts should be referenced by deterministic paths and exposed through stable URLs where possible

7. OPERATOR / USER FLOWS
Running BOQ:
1. Submit `qs.boq_generate` for a `project_id`.
2. 0luka receives and validates the task through submit/dispatch.
3. `qs` runs aggregate, acceptance check, and internal export.
4. If owner-facing export is blocked, the job must surface a blocked state rather than silently continue.

Checking compliance:
1. Submit `qs.compliance_check`.
2. `qs` evaluates rule/acceptance context from project artifacts.
3. Result is a deterministic report with explicit findings.

Generating PO:
1. Submit `qs.po_generate`.
2. Job remains gated until approval is satisfied.
3. On approval, `qs` produces PO artifacts.

Retrieving outputs:
1. Operator reads status and outputs through Mission Control projection and QS-facing result views.
2. Internal artifacts and final artifacts remain distinguishable.

8. 0LUKA INTEGRATION BLUEPRINT
Submission path:
- through [core/submit.py](/Users/icmini/0luka/core/submit.py)

Dispatch path:
- through [core/task_dispatcher.py](/Users/icmini/0luka/core/task_dispatcher.py)

Bridge path:
- high-level mapping through [core/bridge.py](/Users/icmini/0luka/core/bridge.py)

Operator visibility:
- through [tools/ops/mission_control/server.py](/Users/icmini/0luka/tools/ops/mission_control/server.py)

QS must integrate as a contract-based module:
- explicit job contract
- explicit payload inputs/outputs
- explicit blocked/completed/failed states

QS must never own:
- approval engine
- remediation queue
- health supervisor
- dispatcher lifecycle
- global observability authority

9. FILE / MODULE BLUEPRINT
Current anchor files:
- [repos/qs/src/universal_qs_engine/cli.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/cli.py)
- [repos/qs/src/universal_qs_engine/contracts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/contracts.py)
- [repos/qs/src/universal_qs_engine/artifacts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/artifacts.py)
- [repos/qs/src/universal_qs_engine/job_contracts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/job_contracts.py)

Practical product-layer structure on top of current repo:
- domain logic stays under `repos/qs/src/universal_qs_engine/`
- job contracts stay in `repos/qs/src/universal_qs_engine/job_contracts.py`
- tests stay in `repos/qs/tests/`
- product docs stay in `repos/qs/docs/` and `docs/review/`

Near-term additions should separate:
- domain/job contracts
- artifact/result shaping
- status projection
- 0luka integration adapters

10. PHASED IMPLEMENTATION PLAN
Phase A: contracts + status surface
Scope: lock job contracts and shared status model.
Why it matters: prevents drift before queue/runtime coupling.
Dependency: none beyond current QS module.
Stop condition: explicit contracts exist for all four jobs.

Phase B: queue integration
Scope: make `qs.boq_generate` and `qs.compliance_check` consumable through 0luka submission/dispatch paths.
Why it matters: makes QS use the real platform instead of local-only flows.
Dependency: Phase A.
Stop condition: job submission and deterministic result mapping are stable.

Phase C: approval-gated actions
Scope: wire `qs.po_generate` and publish/finalize actions to 0luka approval outcomes.
Why it matters: critical outputs must fail closed.
Dependency: Phase B.
Stop condition: no gated action completes without approval.

Phase D: artifact outputs
Scope: standardize run manifest and artifact bundle structure.
Why it matters: outputs become operator-usable and reproducible.
Dependency: Phase B and C.
Stop condition: each job writes deterministic outputs with stable references.

Phase E: Mission Control visibility
Scope: expose QS job states and artifacts through operator surfaces.
Why it matters: the product must be operable, not just executable.
Dependency: earlier phases.
Stop condition: operators can inspect QS job state and outputs without bypassing 0luka.

11. RISKS / BOUNDARIES
Risks:
- letting QS grow its own runtime semantics
- embedding approval decisions inside QS instead of honoring 0luka gates
- mixing draft/internal artifacts with final publish outputs
- introducing non-deterministic product behavior that bypasses contract tests

Boundaries:
- 0luka owns governance, approval, remediation, health, and dispatch
- `qs` owns business semantics, artifacts, and product-facing job contracts
- all cross-boundary behavior must be explicit and contract-based

12. DEFINITION OF DONE
`qs` is a real product/application layer on top of 0luka when:
- all four jobs have explicit contracts and deterministic states
- BOQ, compliance, PO, and report flows produce domain artifacts
- approval-required actions remain blocked until 0luka clears them
- Mission Control can surface job status and artifacts without QS owning runtime control
- QS can continue implementation without redefining sealed 0luka subsystems

13. FIRST BUILD STEP
The first safe build step is already the correct one: define and lock the four QS job contracts in [repos/qs/src/universal_qs_engine/job_contracts.py](/Users/icmini/0luka/repos/qs/src/universal_qs_engine/job_contracts.py), then build the next thin status/result projection layer on top of those contracts without coupling QS directly to 0luka runtime internals.
