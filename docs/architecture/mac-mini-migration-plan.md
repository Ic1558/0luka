# Mac mini Migration Plan

Migration Status: DESIGN COMPLETE
Verification: COMPLETE
Cutover: READY (not executed)
Rollback readiness: PREPARED

Status: DRAFT  
Scope: Supervisor migration (PM2 -> launchd) for Mac mini host

---

## Purpose

This document is the migration table of contents for the Mac mini supervisor change.  
It links all artifacts, defines the phase sequence, and marks the execution gates.

---

## Architecture Artifacts (Current)

- Decision: docs/architecture/mac-mini-supervisor-decision.md
- Runtime topology: g/reports/mac-mini/runtime_topology.md
- PM2 inventory: docs/architecture/mac-mini-runtime-inventory.md
- Cutover checklist: docs/architecture/mac-mini-cutover-checklist.md
- Runtime doctor: tools/ops/runtime_doctor.zsh
- Launchd wrapper draft: tools/ops/antigravity_controltower_wrapper.zsh
- Launchd plist draft: docs/architecture/drafts/com.antigravity.controltower.plist

---

## Phase Sequence

### Phase 0 — Design Complete ✓

Artifacts created and aligned with machine truth.

Gate: design artifacts reviewed and approved.

### Phase 1 — Verification ✓

Verified:
- launchd crash-loop identified (5,679 runs, exit 1, port 8089 conflict)
- PM2 confirmed as sole live owner of port 8089 (PID 97282)
- Old plist confirmed loaded (system python, wrong CWD, no wrapper)
- Cutover checklist corrected: bootout step added before bootstrap
- Dual-supervisor condition documented: g/reports/mac-mini/dual-supervisor-finding.md

Gate: PASSED.

### Phase 2 — Cutover (not executed)

Use the cutover checklist to transition supervisor ownership.

Gate: launchd owns canonical runtime and health checks pass.

### Phase 3 — Rollback Readiness (not executed)

Rollback steps validated and documented before cutover execution.

Gate: rollback sequence verified as safe and deterministic.

---

## Execution Gate

Current state: CUTOVER READY

No runtime commands may be executed, including:
- launchctl
- pm2
- process termination
- service bootstrap

Runtime mutations may only occur when explicitly authorized by the operator.

Trigger phrase required to enter cutover phase:

ENTER CUTOVER PHASE

---

## Advisory Notes

See also:
docs/architecture/mac-mini-launchd-migration-failure-patterns.md

Review before Phase 2 cutover execution.
