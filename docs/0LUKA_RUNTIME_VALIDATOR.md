# 0LUKA Runtime Validator Specification

File: `docs/0LUKA_RUNTIME_VALIDATOR.md`  
Version: `v1.0`  
Status: `Runtime Verification Spec`

## 1. Purpose

The Runtime Validator verifies that the live runtime instance of 0luka obeys all platform invariants.

It ensures:
- state machine correctness
- artifact integrity
- projection consistency
- approval enforcement
- runtime health

The validator may run in:
- manual operator checks
- CI validation
- runtime health monitoring

## 2. Validation Scope

The validator checks four layers:

| Layer | Verified |
|---|---|
| Kernel invariants | platform laws |
| State machine | valid transitions |
| Runtime invariants | filesystem/state |
| Projection invariants | read model consistency |

## 3. Validator Entry Point

Example CLI:

```bash
python3 tools/ops/runtime_validator.py
```

Optional modes:
- `--quick`
- `--full`
- `--run <run_id>`
- `--artifacts`
- `--json`

## 4. Validation Categories

### 4.1 Runtime State Validation

Validate:
- runtime state schema
- state value validity
- state transition legality

Example rule:

```text
state ∈ {
  INGESTED
  ACCEPTED
  PENDING_APPROVAL
  APPROVED
  EXECUTING
  COMPLETED
  FAILED
  REJECTED
  ARCHIVED
}
```

Illegal state -> validation failure.

### 4.2 State Transition Validation

Check every run transition.

Valid transitions defined in:
- `docs/0LUKA_STATE_MACHINE_SPEC.md`

Example invalid cases:
- `EXECUTING -> ACCEPTED`
- `ARCHIVED -> EXECUTING`
- `INGESTED -> EXECUTING`

### 4.3 Approval Enforcement

Rules:
- `requires_approval = true` -> execution cannot begin before `APPROVED`

Validator must check:
- no `EXECUTING` before approval.

### 4.4 Artifact Integrity

Check:
- `artifact_refs` exist
- artifact paths valid
- artifact located under `artifacts/<run_id>`

Failure examples:
- `artifact_refs` path missing
- artifact outside artifact directory

### 4.5 Truth Source Consistency

Runtime truth:
- runtime sidecar state

Projection:
- Mission Control read model

Validator must check:
- projection matches runtime truth

Mismatch -> projection drift.

### 4.6 Interface Queue Integrity

Check that a task exists in only one queue:
- `interface/inbox`
- `interface/completed`
- `interface/rejected`

Violation example:
- same task in inbox and completed.

### 4.7 Artifact Provenance

Validator must verify:
- `artifact_refs` correspond to completed runs

Invalid case:
- `artifact_refs` present in `FAILED` state.

## 5. Validation Workflow

Validator execution flow:

```text
scan runtime state
        ↓
validate state schema
        ↓
validate transitions
        ↓
validate approvals
        ↓
validate artifacts
        ↓
validate projections
        ↓
generate report
```

## 6. Output Report

Example output:

```text
0LUKA Runtime Validation Report

Runs scanned: 48

State errors: 0
Artifact errors: 0
Approval violations: 0
Projection drift: 0

Runtime status: HEALTHY
```

## 7. Failure Categories

| Category | Meaning |
|---|---|
| `STATE_ERROR` | invalid runtime state |
| `TRANSITION_ERROR` | illegal state transition |
| `APPROVAL_ERROR` | approval rule violation |
| `ARTIFACT_ERROR` | artifact inconsistency |
| `PROJECTION_DRIFT` | read model mismatch |

## 8. Validator Modes

### Quick Mode

`--quick`

Checks:
- state schema
- queue integrity
- dispatcher alive

### Full Mode

`--full`

Checks:
- all runs
- artifact integrity
- projection consistency
- state machine correctness

### Run-specific Mode

`--run <run_id>`

Checks:
- single run correctness

## 9. Integration Points

Runtime validator integrates with:
- CI pipelines
- operator diagnostics
- Mission Control health panel

Example CI step:

```bash
python3 tools/ops/runtime_validator.py --full
```

## 10. Automatic Monitoring

Validator may run periodically.

Examples:
- cron
- launchd
- background monitor

Example schedule:
- every 10 minutes

## 11. Failure Response

If validator detects errors:

Minor:
- log warning
- operator review

Major:
- raise runtime alert
- block execution

## 12. Example Validation Report (JSON)

```json
{
  "runs_scanned": 48,
  "state_errors": 0,
  "transition_errors": 0,
  "artifact_errors": 0,
  "approval_errors": 0,
  "projection_drift": 0,
  "runtime_status": "healthy"
}
```

## 13. Validator Guarantees

If validator passes:
- state machine integrity guaranteed
- artifact provenance guaranteed
- approval safety guaranteed
- projection consistency guaranteed

## 14. Relationship to Other Documents

Validator enforces rules defined in:
- `docs/0LUKA_KERNEL_INVARIANTS.md`
- `docs/0LUKA_STATE_MACHINE_SPEC.md`
- `docs/0LUKA_RUNTIME_INVARIANTS.md`

These documents define what must be true.  
The validator checks that it actually is true.

## Summary

The Runtime Validator is the verification layer of the 0luka platform.

It guarantees that the runtime obeys:
- kernel invariants
- state machine rules
- artifact integrity
- approval safety
- projection correctness

A passing validator means the runtime instance is structurally correct and safe to operate.

Current implementation entrypoint:
- `tools/ops/runtime_validator.py`
