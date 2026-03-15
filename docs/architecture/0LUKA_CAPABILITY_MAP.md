# 0LUKA Capability Map (Canonical Contract)

Status: CANONICAL  
Authority: System Governance Contract  
Scope: Current capabilities only (not roadmap)

This document defines the authoritative capability contract of the 0luka system.

Any implementation, UI surface, or roadmap item must remain consistent with the
capability boundaries defined here.

Changes to this document require governance review.

## Canonical Governance Rules

1. This document describes current system capability only.
2. Future roadmap items must not be added here until implemented.
3. Implementation may not exceed capability authority defined here.
4. Operator interfaces must respect execution boundaries defined here.
5. Any change to capability authority requires governance phase change.

## 1. System Classification

0luka is currently a governed runtime system with:

- deterministic kernel evidence
- explicit policy governance
- supervised runtime remediation
- supervised autonomy candidates
- read-only operator decision intelligence

It is not an autonomous execution platform. It is a supervised runtime governance system with bounded candidate preparation and explicit operator-controlled execution gates.

## 2. Capability Categories

### Kernel Capabilities

- append-only runtime evidence logging
- deterministic execution state projection
- fail-closed runtime safety enforcement
- stable artifact placement in repo/runtime state paths

### Policy Governance Capabilities

- append-only policy proposal ledger
- policy approval, deploy, rollback, and override governance
- active policy version tracking
- policy preflight validation
- policy feedback signals derived from runtime evidence

### Runtime Governance Capabilities

- runtime lane state visibility
- remediation proposal, bridge, approval, and execution chain
- supervised execution with idempotency guards
- multi-lane remediation coordination through explicit `lane_targets`
- execution state and execution observability projections

### Mission Control / Operator Capabilities

- Mission Control read models for runtime, policy, remediation, and candidate state
- explicit operator runtime controls for freeze/pause runtime behavior
- explicit operator actions for candidate promotion and candidate lifecycle management
- explicit operator-gated remediation approval and execution APIs

### Supervised Autonomy Capabilities

- supervised autonomy candidate creation
- candidate ranking and observability
- candidate lifecycle state management
- candidate promotion into the governed remediation lifecycle

### Decision Intelligence Capabilities

- deterministic urgency, impact, recurrence, and risk bands for candidates
- bounded decision hints derived from current evidence only
- compact evidence summaries tied to candidate ranking, feedback, and execution history

## 3. Capability Table

| Capability | Layer | Current State | Authority Level | Execution Boundary | Evidence Surface |
| --- | --- | --- | --- | --- | --- |
| Append-only kernel event logging | Kernel | Active | System | No execution power | `observability/logs/*.jsonl` |
| Deterministic execution state projection | Kernel / Runtime | Active | System | Read model only | execution state projections, execution logs |
| Policy proposal / approval / deploy / rollback / override | Control Plane | Active | Operator-governed | Explicit policy APIs only | policy proposal ledger, version ledger, deployment ledger |
| Policy preflight validation | Control Plane | Active | System + Operator | Blocks invalid deploy/rollback values | policy preflight responses, policy audit events |
| Active policy binding to runtime | Runtime Governance | Active | Policy-governed | Read-only from runtime | active policy surface, policy snapshots |
| Runtime lane recommendation | Runtime Governance | Active | System-prepared, operator-visible | Recommendation only | runtime lane events, policy snapshots, guard telemetry |
| Remediation proposal generation | Runtime Governance | Active | System-prepared | Proposal only, no execution | remediation proposal ledger |
| Remediation selection | Runtime Governance | Active | Operator | Selection only | remediation selection ledger |
| Remediation bridge classification | Runtime Governance | Active | System | `EXECUTION_READY` or `BLOCKED`; no execution | remediation bridge ledger |
| Remediation approval gate | Runtime Governance | Active | Operator | Approval only, no execution | remediation approval ledger |
| Remediation execution | Runtime Governance | Active | Operator | Explicit execute call required | remediation execution ledger |
| Multi-lane remediation execution | Runtime Governance | Active | Operator | Explicit `lane_targets`; per-target-lane execution only | multi-lane execution rows, `execution_group_id` |
| Operator runtime freeze/pause controls | Mission Control / Runtime | Active | Operator | Gates runtime remediation execution only | operator runtime control ledger |
| Supervised autonomy candidate creation | Supervised Autonomy | Active | System-prepared | Candidate only, no promotion/execution | supervised autonomy candidate ledger |
| Candidate promotion to remediation proposal | Supervised Autonomy | Active | Operator | Explicit promotion only | candidate promotion ledger + remediation proposal ledger |
| Candidate lifecycle management | Supervised Autonomy | Active | Operator | Dismiss / resolve / archive only | candidate lifecycle ledger |
| Candidate ranking / observability | Supervised Autonomy | Active | Read-only | No lifecycle or execution power | candidate observability read models |
| Operator decision intelligence | Decision Intelligence | Active | Read-only | Decision support only | decision-support read models |

## 4. Explicit Non-Capabilities

0luka does not currently do the following:

- no automatic policy mutation
- no automatic policy proposal creation
- no automatic policy deploy, rollback, or override
- no autonomous remediation loop
- no automatic remediation execution
- no automatic candidate promotion
- no automatic candidate dismissal, resolution, or archival
- no hidden execution path outside the explicit bridge -> approval -> execute chain
- no distributed bypass of per-runtime idempotency contracts
- no ML, LLM, or probabilistic ranking inside runtime governance or decision support

## 5. Canonical System Invariants

The following invariants are canonical and must remain true:

- candidate lifecycle state must be append-only derived, not mutable row state
- Mission Control controls must never bypass the same API gates used by tests
- multi-lane execution idempotency must remain per-target-lane
- intelligence may recommend, but execution power expands only through explicit governance phases
- every new lane or proposal class must inherit append-only evidence, read models, and fail-closed guards
- runtime may read governed policy, but runtime may not mutate governed policy
- supervised autonomy candidates remain advisory until explicit operator promotion
- remediation execution always requires the governed chain: selection -> bridge -> approval -> explicit execution call

## 6. Authority Scope

This document is the authoritative description of:

- execution authority
- runtime governance boundaries
- operator vs system responsibility
- autonomy limits

If code, UI behavior, or documentation conflicts with this document, this document takes precedence until governance review updates it.

## 7. Current Phase Position

Current position in the implementation tree:

- supervised autonomy layer complete through candidate lifecycle management
- operator decision intelligence active as read-only decision support
- supervised remediation execution active behind explicit bridge, approval, idempotency, and operator runtime control gates

This places 0luka in a supervised autonomy runtime stage, not a self-governing autonomous runtime stage.

## 8. Current System Phase

- Kernel layer: complete
- Runtime governance: active
- Supervised autonomy: active
- Operator decision intelligence: read-only

Current phase: 10.1

## Phase 0 Bridge Evidence Status

- **Phase 0A (Provenance Hashes)** replaced the legacy `"dispatch"` placeholders with deterministic SHA-256 values: `inputs_sha256` reflects the gated task payload accepted through phase1a and `outputs_sha256` is derived from the normalized execution envelope before sealing, removing all `dispatch` placeholders.
- **Phase 0B (Lifecycle Evidence)** adds structured execution lifecycle events (`execution_started` and `execution_finished`) that bind `task_id`, `op_id`/`execution_id`, command, canonical executor identity (`system/agents.lisa_executor.py`), event name, return code, and timestamps while keeping the string-based command/effects lists untouched.
- **Phase 0C (Dispatcher Proof)** completed via `task-phase0c-proof-004` submitted with `ROOT=$(pwd) DISPATCH_LOG=/tmp/dispatcher-phase0c.jsonl DISPATCH_LATEST=/tmp/dispatch_latest-phase0c.json python3 -m core dispatch --file /tmp/task-phase0c-proof-004.yaml`; the run committed, emitted `interface/outbox/tasks/task-phase0c-proof-004.result.json`, and recorded a sealed `0luka.result/v1` envelope with real 64-character provenance hashes and the requested `ls -la` execution logs.
- Dispatch overrides for `DISPATCH_LOG` and `DISPATCH_LATEST` wrote to `/tmp/dispatcher-phase0c.jsonl` and `/tmp/dispatch_latest-phase0c.json`, proving the overridden paths are writable in this environment.
- Phase 0 evidence gap is now closed, and the health, guards, bridge, phase1c/policy, false-authority, execution-hash, and lifecycle validations all passed; this settles the evidence-only barriers so AG-17 / ExecutionEnvelope work may now proceed on top of the sealed Phase 0 foundation.

## AG-17A Slice 1

- AG-17A Slice 1 is complete and was re-verified on the current branch without any new code changes. `ExecutionEnvelope` already exists in `core/execution/execution_envelope.py` as a frozen local dataclass with the required Slice 1 fields: `v`, `execution_id`, `task_id`, `trace_id`, `intent`, `accepted_input`, `routing`, `executor`, `policy`, `wrapper`, `timestamps`, `evidence`, `result`, `provenance`, and `seal`.
- The module already supports `to_dict()`, canonical `to_json()`, and `evidence.execution_events`. Canonical JSON uses `sort_keys=True`, `separators=(",", ":")`, and `ensure_ascii=False`.
- Hash/seal behavior is verified in the existing implementation: `envelope_hash()` excludes `seal`, blanks `provenance["envelope_sha256"]` before hashing, and returns a deterministic SHA-256 hex value; `sealed()` returns a new instance, populates `provenance["envelope_sha256"]`, and sets `seal = {"alg": "sha256", "value": ...}`.
- The focused tests `python3 -m pytest core/verify/test_execution_envelope.py` pass (`3 passed`), proving deterministic serialization, deterministic envelope hashing, dict-shaped seals, populated `provenance["envelope_sha256"]`, preserved `execution_events`, and immutability via the returned sealed instance.
- This remains local schema verification only: dispatcher integration has not started, outbox artifacts do not yet carry `execution_envelope` from this step alone, and AG-17B has not started from this verification pass. Slice 2 remains the next expected refinement step.

## AG-17A Slice 2

- AG-17A Slice 2 extends the local ExecutionEnvelope schema with top-level identity and routing sections while keeping the canonical serialization, dict-shaped seal, populated envelope hash, and evidence execution events introduced in Slice 1.
- Added a `v` field (`"0luka.execution_envelope/v1"`), `trace_id`, and semantic sections for `accepted_input` (capturing the canonical gated task) and `routing` (recording router source, authority match, selected executor, and fallback status).
- Focused tests (`python3 -m pytest core/verify/test_execution_envelope.py`) now pass (`3 passed`) and prove that `v`, `trace_id`, `accepted_input`, and `routing` survive serialization, canonical JSON remains deterministic, and sealing continues to fill `provenance["envelope_sha256"]` while preserving `execution_events`.
- This is still a local dataclass refinement only; dispatcher/router/outbox integration remains pending, and ExecutionEnvelope is not yet the runtime authority object. AG-17B/AG-17C remain future steps once the schema is fully settled.

## AG-17A Slice 3 — Envelope Builder Layer

- AG-17A Slice 3 introduces a local builder layer for `ExecutionEnvelope` to make envelope construction deterministic, repeatable, and less error-prone before any runtime integration begins.
- This slice adds a factory-style API, `ExecutionEnvelope.build(...)`, which constructs a fully validated envelope from explicit inputs while normalizing nested fields into the structured dataclasses introduced in Slice 2.
- The builder accepts either structured dataclasses or plain dictionaries for `routing`, `executor`, `policy`, `wrapper`, `timestamps`, `evidence`, `result`, `provenance`, and `seal`, then normalizes dict inputs into the corresponding dataclasses automatically.
- The builder also applies safe defaults where values are omitted: `v = "0luka.execution_envelope/v1"`, empty `seal`, empty `evidence.commands` / `logs` / `execution_events`, empty `result.status` / `result.summary`, and empty `provenance.inputs_sha256` / `outputs_sha256` / `envelope_sha256`.
- Validation runs on build through the existing `validate()` logic, while hashing and sealing semantics remain unchanged from Slice 1 and Slice 2: canonical JSON serialization, `envelope_hash()` excluding `seal`, blanked `provenance["envelope_sha256"]` during hashing, and `sealed()` returning a new immutable instance.
- Validation: `python3 -m pytest core/verify/test_execution_envelope.py` passes (`7 passed`), confirming builder support for dict and typed inputs, correct safe defaults, validation on invalid input, hash equivalence with manual construction, sealed-instance immutability, and preserved `execution_events`.
- Interpretation boundary: this slice adds a local builder surface only. Dispatcher, router, executor, and `outbox_writer` integration have not started, and AG-17B remains the future phase where runtime components begin constructing `ExecutionEnvelope` instances.

## AG-17A CLOSED

- Final verification concluded **VERDICT A: AG-17A CLOSED**. ExecutionEnvelope now exposes `v`, `trace_id`, `accepted_input`, `routing`, `intent`, `executor`, `policy`, `wrapper`, `evidence.execution_events`, `provenance.envelope_sha256`, and a dict-shaped `seal`, with canonical `to_json()` and `sealed()` populating the envelope hash.
- Structured lifecycle evidence now resides in `evidence.execution_events`, superseding the prior requirement that lifecycle semantics live inside legacy `commands[]`, so the Phase 0 lifecycle gap is considered resolved at the schema layer.
- AG-17A remained a local schema phase—no dispatcher/router/executor/outbox integration occurred, and ExecutionEnvelope is not emitted at runtime. AG-17B dispatcher embedding is now the next permitted phase while AG-17C stays pending.

## AG-17B (embedding complete)

- AG-17B embeds the sealed `ExecutionEnvelope` into the dispatcher-produced result bundle. `core/task_dispatcher.py` now constructs and seals the envelope (intent, accepted_input, routing, executor, policy, wrapper, timestamps, evidence.execution_events, provenance, seal) during `_build_result_bundle()`, and the sealed object is attached under `result_bundle["execution_envelope"]`. `core/outbox_writer.py` preserves this new field through `_ensure_result_envelope()` so that `interface/outbox/tasks/*.result.json` now carries both the legacy top-level `0luka.result/v1` envelope and the embedded authority object.
+ Focused proofs (`python3 -m pytest core/verify/test_execution_envelope.py core/verify/test_execution_envelope_embedding.py`) pass (`5 passed`), confirming the embedded envelope exists, is sealed, contains `execution_events`, and leaves the top-level result shape untouched.
+ AG-17B broader validation is now complete (guards, health, bridge/policy, execution envelope suites, phase8 dispatcher), so the embedding is production-ready. AG-17B = VALIDATED and AG-17C is now permitted while reader migration remains future work.

## AG-17B VALIDATED

- Validation outcome: `check_no_machine_paths.py`, `check_kernel_boundaries.py`, `core/health.py --full`, `core/verify/test_bridge.py`, `core/verify/test_phase1c_gate.py`, `core/verify/test_bridge_false_authority_remediation.py`, `core/verify/test_execution_envelope.py`, `core/verify/test_execution_envelope_embedding.py`, and `core/verify/test_phase8_dispatcher.py` all pass.
- Artifact verification: `interface/outbox/tasks/ag17b-validate-001.result.json` retains `v = "0luka.result/v1"`, `status`, `summary`, `provenance`, and `seal` while carrying the embedded `execution_envelope` (`v = "0luka.execution_envelope/v1"`, a dict-shaped `seal`, `provenance.envelope_sha256`, and `evidence.execution_events` containing `execution_started` + `execution_finished`).
- Architectural interpretation: AG-17B is the first validated runtime integration of the authority object. Dispatcher-produced results emit `execution_envelope` while top-level compatibility is preserved. AG-17C is now allowed to begin but has not yet started.

## AG-17B fix PASS

- Root cause: `_attach_execution_envelope()` in `core/task_dispatcher.py` had been constructing `ExecutionEnvelope(...)` directly with stale nested field shapes, so schema drift in the Slice 2/3 dataclasses could raise `TypeError` during sub-object normalization.
- Fix: the dispatcher now uses `ExecutionEnvelope.build(...).sealed()` and maps only the current schema fields: `routing` uses `router`, `route`, and `policy_version`; `executor` uses `executor_id` and `executor_version`; `policy` uses `policy_id` and `policy_version`; `wrapper` uses `wrapper_name` and `wrapper_version`; `provenance` now passes only the hash payload extracted from `result_bundle["provenance"]["hashes"]`. Stale keys are no longer passed, while `execution_events` is still appended before sealing.
- Validation: `python3 -m pytest core/verify/ -q -k "execution_envelope or attach_execution" --tb=short` passes (`9 passed`), `python3 -m pytest core/verify/ -q --tb=no` passes (`709 passed`), and the proof dispatch `ROOT=$(pwd) LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime python3 -m core dispatch --file /tmp/ag17b_proof.yaml` completed with `status = committed`.
- Proof artifact: `interface/outbox/tasks/ag17b-proof-001.result.json` preserves the top-level `v = "0luka.result/v1"` envelope while embedding `execution_envelope.v = "0luka.execution_envelope/v1"`. The embedded routing keys are exactly `router`, `route`, and `policy_version`; executor keys are exactly `executor_id` and `executor_version`; policy keys are exactly `policy_id` and `policy_version`; `provenance.envelope_sha256` is a 64-character hex value; `seal.alg = "sha256"`; and `evidence.execution_events` contains `execution_started` and `execution_finished`.
- Compatibility boundary: this fix resolves the AG-17B schema-alignment blocker and restores correct builder-based runtime embedding without changing the top-level result envelope contract. It does not remove legacy mirrors or imply completion of AG-17C or later migration/deprecation phases.

## AG-17C1 complete

- AG-17C1 introduces the shared compatibility helpers in `core/result_reader.py`: `get_result_status`, `get_result_summary`, `get_result_provenance_hashes`, `get_result_seal`, `get_result_execution_events`, `get_result_executor_identity`, `get_result_routing`, and `detect_result_authority_mismatches`. All helpers prefer `execution_envelope.*` and fall back to legacy top-level fields without mutating the artifact.
- The mismatch detector reports structured entries (`{"field": ..., "envelope": ..., "legacy": ...}`) for disagreements in status, summary, provenance hashes, and seal.
- Focused tests (`python3 -m pytest core/verify/test_result_reader.py`) now pass, proving envelope-first reads, fallback behavior, execution-event extraction, executor/routing extraction, mismatch reporting, and immutability; the AG-17A/B envelope suites and guards still pass as before.
- This is still a helper layer; AG-17C2 reader adoption has not started, no major readers have migrated, and top-level fields remain untouched for compatibility. AG-17C2 is now the next permitted phase.

## AG-17C2 complete

- AG-17C2 migrates `core/health.py` and `core/verify/test_phase8_dispatcher.py` to the helper layer: health now calls `get_result_status`, `get_result_summary`, `get_result_provenance_hashes`, `get_result_seal`, and `get_result_execution_events` (plus mismatch detection) while `test_phase8_dispatcher` validates artifacts via the same helpers instead of direct top-level lookups; `core/verify/test_result_reader.py` continues proving envelope-first reads, fallback behavior, mismatch reporting, and immutability.
- These readers now prefer the embedded `execution_envelope` while still working when the envelope is absent. Backward compatibility is preserved, and mismatch-aware behavior is exercised in a real reader slice.
- AG-17C2 is a narrow, low-risk reader adoption; AG-17C3 (legacy-field cleanup/deprecation) is now the next permitted phase but has not yet started.

## AG-17 re-baseline

- Current AG-17 stage status:

| Stage | Status |
|---|---|
| AG-17A foundation | COMPLETE |
| AG-17B embedding/fix | COMPLETE |
| AG-17C1 helper alignment | COMPLETE |
| AG-17C2 reader adoption | COMPLETE |
| AG-17D | CLOSED (Decision B semantics) |

- Re-baseline evidence: `core/execution/execution_envelope.py` now carries the structured `ExecutionEnvelope` stack (`build()`, `validate()`, canonical `to_json()`, deterministic `envelope_hash()`, and `sealed()`), `core/task_dispatcher.py` constructs the embedded envelope through `ExecutionEnvelope.build(...).sealed()` inside `_attach_execution_envelope()`, `core/result_reader.py` provides helper APIs for status, summary, provenance hashes, seal, execution events, routing, executor identity, and policy, and real reader surfaces now consume the helper layer in `core/health.py`, `core/phase1d_result_gate.py`, `core/verify/test_phase8_dispatcher.py`, `core/verify/test_task_dispatcher.py`, and `core/verify/test_phase15_5_2_timeline_heartbeat.py`.
- Decision B closeout: AG-17 closed under Decision B semantics: embedded `execution_envelope.provenance.outputs_sha256` and top-level `provenance.hashes.outputs_sha256` represent different integrity scopes and are not required to match. AG-17 therefore closes by semantic clarification rather than by runtime redesign.
- Docs re-sync note: this capability map had been stale because it still recorded `AG-17D1 next` and described the remaining gap as “embedded envelope sealed with `outputs_sha256 = \"\"`.” The current branch no longer hardcodes that path. The evidence pack in `evidence/ag17/` is now the permanent closeout record for the different-scope hash semantics.
- Remaining open items:
  - Follow-up hygiene only: other docs and stale test expectations may still need alignment to Decision B semantics.
  - Permanent evidence pack: preserve `evidence/ag17/` as the closeout verification record.
- Next action: repository alignment only. AG-17A/B/C are effectively complete, AG-17D is closed under Decision B semantics, and no runtime redesign is implied by this update.

## AG-17 closeout verification

- Runtime findings: `core/task_dispatcher.py` precomputes `result_bundle["provenance"]["hashes"]["outputs_sha256"]` from the result-bundle outputs/artifacts payload, then `_attach_execution_envelope()` seals that value into `execution_envelope.provenance.outputs_sha256`. `core/outbox_writer.py` later recomputes the top-level `provenance.hashes.outputs_sha256` from the normalized outer result envelope with `outputs_sha256` blanked and `seal` removed. `core/execution/execution_envelope.py` itself is deterministic and does not introduce the mismatch; the divergence comes from the two different hash scopes.
- Runtime proof evidence is captured under `evidence/ag17/README.md`, `evidence/ag17/ag17_closeout_summary.json`, and `evidence/ag17/ag17_closeout_runtime_artifact.json`. Observed values: embedded `execution_envelope.provenance.outputs_sha256 = 09ddbe3722769c3116595547b066755590ebeda5203a00fa7835209ecf9a03bc`, final top-level `provenance.hashes.outputs_sha256 = 9b98cdff8cf1c3eb4d48e87e8aaa3b1bd3696c6c0f9967a36d4ac4cb037a054f`, equality = `false`.
- Decision B: embedded and final top-level outputs hashes are intentionally different-scope integrity signals, and equality between them is **not** a required runtime invariant. The embedded envelope hash covers the pre-outbox result-bundle outputs/artifacts scope, while the top-level artifact hash covers the normalized outer result-envelope scope.
- Closeout interpretation: both hashes are valid integrity signals under the current runtime, and they must not be compared for equality as a correctness requirement. `core/verify/test_execution_envelope_embedding.py` proves pre-outbox bundle/envelope alignment; it does not prove final persisted artifact equality and is not required to.
- Status outcome: **AG-17 closeout status = CLOSED under Decision B semantics**. AG-17A/B/C are effectively complete, AG-17D is closed by semantic clarification rather than runtime redesign, and this decision does not imply schema changes, reader rollback, or legacy mirror removal. `evidence/ag17/` is the permanent closeout evidence pack.

## ExecutionEnvelope Integrity Model (Post-AG-17)

- **Embedded envelope integrity**: `execution_envelope.provenance.outputs_sha256` records the integrity of the dispatcher-produced result bundle before outbox emission. This is the sealed pre-outbox authority signal carried inside the embedded `ExecutionEnvelope`.
- **Artifact integrity**: `provenance.hashes.outputs_sha256` records the integrity of the final normalized artifact written by `core/outbox_writer.py`. This is the persisted artifact-level integrity signal for the outer `0luka.result/v1` envelope.
- **Scope distinction**: the embedded hash and the artifact hash cover different objects. The embedded hash covers the pre-outbox bundle outputs/artifacts scope; the artifact hash covers the normalized persisted result envelope scope after outbox normalization.
- **Equality rule**: because the two hashes cover different scopes, equality is not required and must not be used as a correctness check. Both hashes are valid integrity signals inside their own scope.
- **Decision B reference**: AG-17 closed under Decision B semantics. AG-17 closed by semantic clarification, not runtime redesign.
- **Evidence reference**: the runtime proof for this model is preserved in `evidence/ag17/`, especially `evidence/ag17/ag17_closeout_runtime_artifact.json` and `evidence/ag17/ag17_closeout_summary.json`.

## Legacy Mirror Retirement (Next Architecture Line)

- Phase 1: mirror-read inventory and guard preparation. See `docs/architecture/LEGACY_MIRROR_INVENTORY.md` for the current canonical-reader set, remaining mirror dependencies, and ambiguous sites that still need review before any retirement work begins.

## AG-17C3A complete

- AG-17C3A adds the warning-mode guard `tools/guards/check_result_reader_usage.py`, which scans Python readers for direct legacy accesses (`result["status"]`, `.get("summary")`, etc.), prints matches, and exits 0 so the rest of the migration can breathe.
- AG-17C3A also migrates the easy surface `core/verify/test_phase15_5_2_timeline_heartbeat.py` to the helper APIs (`get_result_status`, plus mismatch handling) and patches `DISPATCH_LOG`/`DISPATCH_LATEST` so it still runs in the sandbox.
- Validation proof: `python3 tools/guards/check_result_reader_usage.py core` now runs (reporting remaining legacy reads), `python3 -m pytest core/verify/test_result_reader.py` passes, and `LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime python3 -m pytest core/verify/test_phase15_5_2_timeline_heartbeat.py` passes.
- Legacy-field removal and schema deprecation have not started; hotspots such as `core/outbox_writer.py`, `core/task_dispatcher.py`, QS tests, and dashboards still read top-level fields directly. AG-17C3B (cleaning these) is now the next permitted phase.

## AG-17C3B-1a complete

- AG-17C3B-1a migrates only the status path inside `core/phase1d_result_gate.py`: `_enforce_evidence_minimum()` now imports `get_result_status` and uses it instead of reading `result["status"]` directly, while the rest of the gate (summary/provenance/seal/evidence handling) remains unchanged and no mismatch logging was added.
- Validation: `python3 tools/guards/check_no_machine_paths.py` and `python3 tools/guards/check_kernel_boundaries.py` pass, `python3 tools/guards/check_result_reader_usage.py core` still runs in warning mode reporting remaining legacy readers, and the helper tests (`python3 -m pytest core/verify/test_result_reader.py` and `python3 -m pytest core/verify/test_phase1d_result_gate.py`) pass.
- This is a deliberately small won-field migration; AG-17C3B is still open, `core/verify/test_task_dispatcher.py` and other gate logic have not yet been migrated, and no legacy-field removal has started. The next expected slice is AG-17C3B-1b or AG-17C3B-2.

## AG-17C3B-1c complete

- AG-17C3B-1c migrates the provenance-hash read path inside `core/phase1d_result_gate.py`: `_enforce_evidence_minimum()` now imports `get_result_provenance_hashes` and uses helper-based envelope-first provenance hash resolution instead of direct `result.get("provenance")` / `provenance.get("hashes")` access. Existing `hash_ok` behavior remains unchanged and still checks only `inputs_sha256` and `outputs_sha256`.
- No direct seal-path migration occurred in this slice because `core/phase1d_result_gate.py` had no direct seal read to replace. No mismatch-reporting behavior was added here, and the status logic from AG-17C3B-1a plus the summary logic from AG-17C3B-1b remain intact.
- Validation: `python3 tools/guards/check_no_machine_paths.py` and `python3 tools/guards/check_kernel_boundaries.py` pass, `python3 tools/guards/check_result_reader_usage.py core` still runs in warning mode reporting remaining legacy readers, and the helper tests (`python3 -m pytest core/verify/test_result_reader.py` and `python3 -m pytest core/verify/test_phase1d_result_gate.py`) pass.
- AG-17C3B is still open: `core/verify/test_task_dispatcher.py` and other medium-risk surfaces have not been migrated, the guard remains warning-mode only, and no legacy-field removal has started. The next expected slice is AG-17C3B-2.

## AG-17C3B-2 complete

- AG-17C3B-2 migrates `core/verify/test_task_dispatcher.py` to helper-layer status reads by replacing direct legacy status access with `get_result_status`. The migrated assertions preserve the same dispatcher semantics: equality checks, membership checks, conditional branches on `committed` / `rejected` / `error`, and the `good_result` / `bad_result` paths.
- Validation: `python3 tools/guards/check_no_machine_paths.py` and `python3 tools/guards/check_kernel_boundaries.py` pass, `python3 tools/guards/check_result_reader_usage.py core` still runs in warning mode and reports remaining legacy readers, and the focused suites (`python3 -m pytest core/verify/test_result_reader.py`, `python3 -m pytest core/verify/test_phase1d_result_gate.py`, and `python3 -m pytest core/verify/test_task_dispatcher.py`) all pass.
- Scope boundary: no runtime logic changed, no schema or artifact structure changed, and no other field family was migrated in this slice. Backward compatibility remains intact because `get_result_status` falls back to the legacy top-level status when `execution_envelope` is absent.
- AG-17C3B remains open pending closeout review. Legacy-field removal has not started, the guard is still warning-mode only, and direct-reader hotspots still remain in `core/outbox_writer.py`, `core/task_dispatcher.py`, direct reads in `core/health.py`, `core/ledger.py`, `core/cli.py`, `core/verify/test_watchdog.py`, `core/verify/test_phase8_dispatcher.py`, the QS repo tests, and dashboard/operator surfaces. The next expected step is AG-17C3B closeout review.

## AG-17C3B closeout review

- AG-17C3B migration slices are complete: AG-17C3A, AG-17C3B-1a, AG-17C3B-1b, AG-17C3B-1c, and AG-17C3B-2 together moved helper-layer authority adoption into `core/phase1d_result_gate.py`, `core/verify/test_phase15_5_2_timeline_heartbeat.py`, and `core/verify/test_task_dispatcher.py`, covering status, summary, and provenance-hash reads in medium-risk surfaces without changing runtime semantics.
- Validation across the slices succeeded: `python3 tools/guards/check_no_machine_paths.py`, `python3 tools/guards/check_kernel_boundaries.py`, `python3 tools/guards/check_result_reader_usage.py core`, `python3 -m pytest core/verify/test_result_reader.py`, `python3 -m pytest core/verify/test_phase1d_result_gate.py`, and `python3 -m pytest core/verify/test_task_dispatcher.py` all ran successfully. The result-reader guard remains warning-mode only and continues to report remaining legacy readers.
- AG-17C3B did not remove legacy top-level fields, change dispatcher runtime logic, change result schemas, migrate dashboards or operator tools, migrate the QS repo, or retire legacy mirrors. Remaining hotspots still include `core/outbox_writer.py`, `core/task_dispatcher.py`, `core/health.py`, `core/ledger.py`, `core/cli.py`, `core/verify/test_watchdog.py`, `core/verify/test_phase8_dispatcher.py`, QS tests, and dashboard/operator surfaces.
- Closeout outcome: AG-17C3B successfully validated helper-layer authority adoption in the intended medium-risk slices while preserving backward compatibility and architectural boundaries. Legacy mirror retirement has not started; the next phase must explicitly decide whether and how mirror deprecation should proceed.

## Legacy Mirror Retirement Readiness

- Retirement readiness verdict: **NOT READY**. Too many authoritative readers still consume legacy top-level mirrors directly or partially, making retirement unsafe and hard to roll back cleanly. Remaining hotspots include `core/outbox_writer.py`, `core/task_dispatcher.py`, `core/health.py`, `core/ledger.py`, `core/cli.py`, `core/verify/test_watchdog.py`, `core/verify/test_phase8_dispatcher.py`, QS repo tests, and dashboard/operator surfaces.
- Remaining hotspot inventory:

| Surface | Risk | Why still risky | Helper migration status |
|---|---|---|---|
| core/outbox_writer.py | High | Normalizes and emits result artifacts; any mistake changes persisted contract | Not migrated |
| core/task_dispatcher.py | High | Produces dispatcher results and CLI-facing statuses; tightly coupled to runtime flow | Not migrated |
| core/health.py | Medium | Operator-facing health/status path; partial legacy reads remain | Partially migrated |
| core/ledger.py | Medium | Aggregates result state and summaries; still reads top-level status/summary directly | Not migrated |
| core/cli.py | Medium | User-facing command path; depends on ledger/health semantics | Not migrated |
| core/verify/test_watchdog.py | Low-medium | Test-only, but still asserts legacy fields directly | Not migrated |
| core/verify/test_phase8_dispatcher.py | Medium | Dispatcher proof surface; changing it needs care to preserve semantics | Partially migrated |
| QS repo tests | High | Separate test estate; unknown downstream assumptions about top-level mirrors | Not migrated |
| Dashboard / operator surfaces | High | Broad reader estate with user-visible impact | Not migrated |

- Guard escalation plan:
  - Warning mode: current state. `check_result_reader_usage.py` reports remaining direct legacy reads and exits 0.
  - Soft fail / CI advisory: next stage. New direct legacy reads should be flagged separately and may fail only when introduced outside an allowlist or baseline, preventing new debt without breaking the backlog.
  - Hard fail: only after core readers and high-risk surfaces are helper-migrated. At that point, direct legacy reads outside explicit exceptions should fail CI.
- Legacy mirror retirement plan:

| Stage | Scope | Safe? | Preconditions |
|---|---|---|---|
| Stage R1 | Finish helper migration for core runtime-adjacent readers (`core/health.py`, `core/ledger.py`, `core/cli.py`, `core/verify/test_watchdog.py`, `core/verify/test_phase8_dispatcher.py`) | Yes | Guard still warning/advisory; no field removal |
| Stage R2 | Migrate emitters/normalizers that still reason about top-level mirrors (`core/outbox_writer.py`, `core/task_dispatcher.py`) to treat `execution_envelope` as primary while still emitting mirrors | Conditionally | R1 complete; mismatch monitoring in place; dedicated regression coverage |
| Stage R3 | Migrate external/high-risk consumers (QS tests, dashboards/operator surfaces) | Conditionally | R2 complete; guard upgraded to advisory or partial block |
| Stage R4 | Freeze new direct legacy reads and turn guard blocking for non-allowlisted files | Yes | Most hotspots gone; stable helper usage everywhere |
| Stage R5 | Start explicit legacy mirror retirement slice for specific low-value mirrors only | Not yet | All above complete; artifact versioning/rollback plan approved |

- AG-17 status note: AG-17A/B/C are complete and AG-17D is closed under Decision B semantics. Any remaining work here is repository hygiene only (docs/test alignment), not additional AG-17 runtime work.
- Interpretation boundary: legacy mirror retirement is still not authorized by this decision alone. AG-17 closed by semantic clarification rather than runtime redesign, and the remaining work in this area is follow-up hygiene rather than reader adoption or schema change.

## 9. Safety Boundary Summary

The following remain operator-only:

- policy proposal approval, deploy, rollback, and override
- candidate promotion
- candidate dismissal, resolution, and archival
- remediation approval for execution
- remediation execution
- operator runtime freeze / unfreeze and pause / resume actions

The system may:

- observe
- summarize
- rank
- recommend
- classify bounded remediation candidates

The system may not:

- promote automatically
- approve automatically
- execute automatically
- mutate policy automatically

## 10. Current Surfaces Tied To This Contract

This capability map corresponds to the current tree’s active surfaces:

- Mission Control policy, runtime lane, remediation, candidate, and decision-support panels
- read-only runtime and policy feedback projections
- explicit POST-only governance actions for promotion, lifecycle, approval, runtime control, and supervised execution
- append-only evidence ledgers across policy, runtime, remediation, and supervised autonomy layers

## 11. Repo Protection Note

This file should be treated as a protected architecture governance document.

Recommended repository handling:

- PR review required for changes to this file
- architecture tag required on PRs that modify this file

This phase records the protection requirement as part of the contract. It does not add new repository enforcement machinery.

## 12. Contract Intent

This document is the canonical current-state capability contract for:

- roadmap interpretation
- implementation boundary checks
- operator expectation setting
- future phase reviews

It describes what 0luka can do now, what remains operator-gated, and what the system explicitly does not do.
