# 0LUKA Master DoD Checklist

File: `docs/0LUKA_MASTER_DOD_CHECKLIST.md`  
Version: `v1.0`  
Status: `DoD Source of Truth`

## Purpose

This checklist defines the consolidated Definition of Done (DoD) status across the 0luka platform.

It follows three core rules:
- Design != Execution
- No Evidence = NOT PROVEN
- Gate controls progression, not optimism

It separates work into:
- `DONE` (implemented + proven)
- `PARTIAL` (implemented in scope, not fully sealed)
- `SPEC ONLY` (documented, no runtime proof)
- `FUTURE` (roadmap, not started/proven)

## Baseline Scope

This checklist reflects the current verified architecture baseline:
- 0luka = runtime / governance / control plane
- QS = application layer above 0luka
- runtime/policy/approval/health/self-healing ownership remains in 0luka

## Master Status Matrix

| Domain | Status | Evidence Standard |
|---|---|---|
| Kernel / Dispatcher / Submit / Runtime Gate | `DONE` | proven runtime behavior |
| QS as application layer | `DONE` | boundary respected |
| QS Product Slice v1 | `DONE` | verified live slice |
| Artifact truth path (QS scope) | `DONE` | runtime truth-path consistency proven |
| Approval for PO flow | `DONE` | proven scoped approval path |
| Mission Control QS read-model | `DONE` | scoped QS endpoint visibility proven |
| Governance Freeze | `SEALED` | repo-level freeze manifest exists and baseline is tag-anchored in outer and nested repos |
| Mission Control system-wide | `PARTIAL` | feed/status/timeline/dashboard rendering proven in read-model scope; full product UI closure not claimed |
| Observability expansion / feed index / analytics | `PARTIAL` | feed guard/index implemented; analytics layer still open |
| Runtime Validator | `PARTIAL` | executable validator exists; broader platform coverage still incomplete |
| Runtime Guardian | `PARTIAL` | validator-driven guardian implementation exists in safe action scope |
| Security model | `PARTIAL` / `SPEC` | some controls proven, broad enforcement not proven |
| Deployment model | `PARTIAL` | some live ops reality exists, full parity not proven |
| Multi-engine ecosystem | `FUTURE` | not started/proven |

## DoD Delta Update

| Domain | Previous | New | Evidence | Notes |
|---|---|---|---|---|
| Runtime Validator | `SPEC ONLY` | `PARTIAL / IMPLEMENTED IN QS SCOPE` | `tools/ops/runtime_validator.py`, `core/verify/test_runtime_validator.py` | QS-focused coverage only; non-QS/full-platform not yet covered |
| Runtime Guardian | `SPEC ONLY` | `PARTIAL / IMPLEMENTED IN SAFE ACTION SCOPE` | `tools/ops/runtime_guardian.py`, `core/verify/test_runtime_guardian.py` | validator-driven logging/escalation proven; destructive/self-healing recovery not yet proven |
| Activity Feed Guard / Index | `PARTIAL / NOT PROVEN` | `PARTIAL / IMPLEMENTED IN OBSERVABILITY SCOPE` | `core/activity_feed_guard.py`, `tools/ops/activity_feed_indexer.py`, `tools/ops/activity_feed_query.py`, feed evidence tests | append-only/index evidence proven; analytics/system-wide consumption still incomplete |
| Mission Control Feed Consumption | `PARTIAL` | `PARTIAL / PROVEN IN READ-MODEL SCOPE` | `interface/operator/mission_control_server.py`, `tools/mission_control.py`, mission control feed tests | activity/feed summary consumption proven; full operator dashboard closure still open |
| Mission Control Dashboard Closure | `PARTIAL` | `PARTIAL / PROVEN IN DASHBOARD SCOPE` | `core/verify/test_mission_control_dashboard_closure.py`, mission control endpoint/read-model tests | system status, activity, remediation, and approval timeline rendering proven; full product UI semantics still open |
| Governance Freeze Seal | `PARTIAL / REPO FREEZE ACTIVE` | `SEALED / TAG-ANCHORED BASELINE` | `core/governance/0luka_platform_frozen_manifest.yaml`, `docs/governance/FREEZE_0LUKA_PLATFORM_v1.md`, `core/verify/test_0luka_governance_freeze_seal.py`, baseline tags | outer and nested repo baselines anchored independently |

## Detailed DoD Gates

### A. Kernel / Runtime Foundation

Status: `DONE` / `PROVEN`

Done when:
1. Dispatcher execution loop works in live runtime.
2. Submit gate rejects invalid payload before inbox.
3. Runtime gate blocks missing `requires` conditions.
4. Lifecycle ordering is `started -> completed -> verified`.
5. Inbox hygiene handles malformed YAML without dispatcher crash.
6. Activity feed linter passes.
7. Proof pack is generated.
8. No kernel regression.

### B. Governance Freeze

Status: `SEALED` / `TAG-ANCHORED BASELINE`

Done when:
1. Kernel tag/freeze boundary exists.
2. Freeze documentation is complete.
3. Canonical interfaces are locked.
4. Design/proof separation is explicit.
5. Runtime vs app ownership has no ambiguity.

Current:
- contractual freeze list exists
- compatibility rules are declared
- runtime/app ownership boundary is explicitly frozen in repo
- outer runtime baseline is tag-anchored
- nested QS baseline is tag-anchored independently

### C. Mission Control Core

Status: `PARTIAL`

Done when:
1. Read model exists for system status.
2. Operator surface reads truth without fabrication.
3. Views include activity feed, task timeline, worker status.
4. Mission Control binds to correct source of truth.
5. No route-signature mismatch on primary routes.
6. Read-model remains non-mutating.

Note:
- QS projection endpoints are proven in scope.
- activity/feed consumption is now proven in read-model scope.
- system-wide dashboard rendering is now proven in dashboard scope.
- full product/UI closure is not proven yet.

### D. Activity Feed / Observability

Status: `PARTIAL`

Done when:
1. `activity_feed.jsonl` is append-only canonical truth.
2. Lifecycle ordering is enforced.
3. Feed linter detects violations.
4. Feed immutability guard exists.
5. Feed index is built and consumed.
6. No stale-log misread.

Current:
- canonical feed + linter: done
- immutability guard: implemented with proof-backed evidence
- feed index: implemented with proof-backed evidence
- analytics layer: not proven

Evidence:
- `core/activity_feed_guard.py`
- `tools/ops/activity_feed_indexer.py`
- `tools/ops/activity_feed_query.py`
- `core/verify/test_activity_feed_guard_evidence.py`
- `core/verify/test_activity_feed_index_evidence.py`
- `core/verify/test_pack10_index_sovereignty.py`

### E. QS as Application Layer

Status: `DONE`

Done when:
1. QS remains app layer and does not absorb kernel responsibilities.
2. runtime/policy/approval/health/self-healing stay in 0luka.
3. Integration uses explicit contracts only.
4. Domain logic stays in QS.
5. Operator visibility goes through Mission Control.

### F. QS Product Slice v1

Status: `DONE` (slice scope) / `PARTIAL` (full blueprint scope)

Done for v1 slice when:
1. Deterministic registry exists.
2. Four core handlers exist.
3. Unknown job fails closed.
4. Jobs run via live runtime path.
5. Approval-required jobs run only post-approval.
6. Artifact refs persist through truth path.
7. Mission Control reflects runtime truth.
8. No runtime-control redesign during implementation.

Scope note:
- v1 slice proven
- full product blueprint depth still open (factor_f, richer compliance/BOQ/estimate depth)

### G. Approval / Policy

Status: `PARTIAL`

Done when:
1. Critical write actions are approval-gated.
2. Approval state is separate from QS terminal status.
3. Pre-approval execution cannot occur.
4. Post-approval execution works.
5. Rejection does not fabricate artifacts.
6. Approval decisions are traceable.

Current:
- `qs.po_generate` path proven
- broader approval classes not fully covered

### H. Operator Visibility / UX

Status: `PARTIAL`

Done when:
1. Operators can see jobs, states, artifacts, and block reasons.
2. Approval queue is visible.
3. Mission Control uses runtime read-model truth.
4. Worker/runtime status is visible.
5. Feed/timeline/system status are visible.
6. Operator actions are auditable.

Current:
- QS run/operator visibility is proven
- feed/status/timeline/dashboard rendering is proven in read-only dashboard scope
- broader product-grade Mission Control closure remains open

### I. Validator / Guardian / Self-Healing

Status: `PARTIAL`

Done when:
1. Runtime validator has executable implementation.
2. Validator checks state, transitions, approvals, artifacts, projection.
3. Guardian runs as real process/daemon.
4. Recovery actions are proven safe in runtime.
5. Validator/guardian emit operational evidence.
6. No self-healing claims without runtime proof.

Current:
- runtime validator implemented in QS scope with proof-backed checks for queue integrity, QS run schema/state, approval consistency, artifact reference integrity, and Mission Control/outbox projection consistency
- runtime validator evidence is backed by:
- `tools/ops/runtime_validator.py`
- `core/verify/test_runtime_validator.py`
- `core/verify/test_qs_bridge_ingress_runtime.py`
- `core/verify/test_qs_approval_gate_runtime.py`
- `core/verify/test_qs_mission_control_projection.py`
- `core/verify/test_qs_runtime_job_registry_wiring.py`
- strict artifact existence remains opt-in via `--artifacts`
- broader non-QS/full-platform invariant coverage remains incomplete
- runtime guardian implemented in safe action scope with validator-driven logging/escalation
- guardian evidence is backed by:
- `tools/ops/runtime_guardian.py`
- `core/verify/test_runtime_guardian.py`
- current guardian actions are limited to `none`, `report_only`, and `freeze_and_alert`
- destructive or automatic repair actions are not yet proven

### J. Security Model

Status: `PARTIAL` / `SPEC`

Done when:
1. Execution isolation is enforced.
2. Direct runtime state mutation is blocked.
3. Artifact immutability is enforced.
4. Approval actions are auditable.
5. Trust boundaries are enforced in runtime.
6. Sensitive artifact access is controlled.

### K. Deployment / Production Ops

Status: `PARTIAL`

Done when:
1. Dispatcher runs under formal service manager.
2. Restart/recovery path is standardized.
3. Operator runbook is usable in live ops.
4. Health/incident flow is operational.
5. Deployment model has live single-node parity.
6. Worker scaling/distributed models are clearly separated from blueprint.

## Tiered Execution Plan

### Tier 1 - Proven Now

Closed scope. Do not reopen without incident evidence.
- kernel runtime baseline
- QS v1 verified slice
- scoped QS projection and artifact truth path

### Tier 2 - Must Implement to Match Existing Docs

Required to align runtime reality with current specifications.
- governance freeze seal
- feed immutability guard
- feed index builder
- runtime guardian minimal live implementation
- system-wide Mission Control observability surfaces

Priority note:
- feed immutability/index evidence should come before guardian implementation because it closes an older truth-layer gap with lower runtime risk.

Progress note:
- feed immutability/index evidence is now implemented in observability scope; next leverage point is guardian minimal live implementation or broader system-wide Mission Control/feed consumption proof.

### Tier 3 - Platform Expansion

Planned growth scope.
- high-volume run validation
- worker scaling
- multi-engine ecosystem rollout
- artifact indexing and analytics

## DoD Progression Rule

A domain can move status only when evidence exists:
- `SPEC ONLY -> PARTIAL`: implementation exists with scoped verification
- `PARTIAL -> DONE`: full gate conditions satisfied with runtime proof

No status may be upgraded using design intent alone.

## Review Cadence

Recommended operational cadence:
- update checklist on each milestone closure
- attach evidence links per promoted domain
- reject status promotion without proof artifacts

## Summary

This document is the execution-facing DoD map for 0luka.

It defines what is proven, what is partial, what is spec-only, and what is future scope, so platform progression remains evidence-based and deterministic.
