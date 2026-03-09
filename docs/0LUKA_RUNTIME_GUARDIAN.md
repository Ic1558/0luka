# 0LUKA Runtime Guardian

File: `docs/0LUKA_RUNTIME_GUARDIAN.md`  
Version: `v1.0`  
Status: `Runtime Protection Layer`

## 1. Purpose

Runtime Guardian is the self-healing control layer of the 0luka platform.

Its role is to:
- monitor runtime integrity
- react to validator failures
- protect system invariants
- recover runtime automatically when possible

Guardian ensures the platform remains safe and operational even when runtime anomalies occur.

## 2. Guardian Position in Architecture

System control hierarchy:

```text
Kernel Invariants
        ↓
Runtime Validator
        ↓
Runtime Guardian
        ↓
Runtime Execution
```

Responsibilities:

| Component | Role |
|---|---|
| Kernel Invariants | define platform laws |
| Runtime Validator | detect violations |
| Runtime Guardian | enforce and repair |

## 3. Guardian Responsibilities

Guardian must perform four functions:

1. Runtime Monitoring

Continuously observe:
- runtime state
- queue integrity
- artifact health
- dispatcher process

2. Violation Detection

Guardian reads results from:
- runtime validator
- activity logs
- state transitions

Violations include:
- state machine violation
- missing artifacts
- approval bypass
- projection drift

3. Automatic Recovery

Guardian attempts automatic correction when safe.

| Problem | Recovery |
|---|---|
| dispatcher crashed | restart dispatcher |
| task stuck in inbox | re-dispatch |
| projection drift | rebuild projection |
| artifact missing | mark run FAILED |

4. Escalation

If recovery is unsafe:
- alert operator
- freeze affected run
- log incident

## 4. Guardian Execution Loop

Guardian operates continuously.

Example loop:

```python
while True:
    run_runtime_validator()

    if validator_errors:
        classify_error()
        attempt_recovery()
        log_action()

    sleep(interval)
```

Typical interval:
- 5-10 minutes

## 5. Guardian Error Classification

Errors detected by validator are grouped into categories.

| Category | Meaning |
|---|---|
| `STATE_ERROR` | invalid runtime state |
| `TRANSITION_ERROR` | illegal state transition |
| `APPROVAL_ERROR` | approval bypass |
| `ARTIFACT_ERROR` | artifact integrity failure |
| `PROJECTION_DRIFT` | read model mismatch |
| `QUEUE_ERROR` | queue corruption |

## 6. Recovery Actions

### Dispatcher Failure

Symptoms:
- no tasks processed
- dispatcher process missing

Recovery:
- restart dispatcher

Example command:

```bash
launchctl kickstart -k gui/$UID/com.0luka.dispatcher
```

### Queue Corruption

Symptoms:
- task appears in multiple queues

Recovery:
- move task to rejected
- log error

### Projection Drift

Symptoms:
- Mission Control state differs from runtime sidecar

Recovery:
- rebuild projection

### Artifact Integrity Failure

Symptoms:
- `artifact_refs` exist but files missing

Recovery:
- mark run `FAILED`
- invalidate artifacts

### Approval Bypass

Symptoms:
- `EXECUTING` without approval

Recovery:
- halt execution
- flag security violation

## 7. Recovery Safety Rules

Guardian must obey strict safety constraints.

### Non-Destructive Principle

Guardian must never delete runtime state automatically.

Allowed actions:
- restart process
- rebuild projection
- mark run `FAILED`
- pause execution

### Truth Source Protection

Guardian must never modify:
- runtime sidecar state
- artifact files

without explicit rules.

### Isolation

Recovery actions must only affect the specific run involved.

## 8. Guardian Logging

Every guardian action must be logged.

Example event:

```json
{
  "event": "guardian_recovery",
  "run_id": "run_20260309_001",
  "issue": "artifact_missing",
  "action": "mark_failed",
  "timestamp": "2026-03-09T03:00:00Z"
}
```

Log location:
- `logs/activity_feed.jsonl`

## 9. Operator Escalation

If guardian cannot recover automatically:
- freeze run
- create incident record
- notify operator

Example escalation:
- `RUN_REQUIRES_MANUAL_REVIEW`

## 10. Integration with Mission Control

Mission Control v2 should expose guardian information.

Dashboard panel:
- runtime health
- guardian actions
- recent incidents
- recovery attempts

## 11. Guardian Deployment

Guardian may run as:
- background daemon
- launchd service
- sidecar process

Example service:
- `com.0luka.guardian`

## 12. Future Expansion

Guardian may later support:
- predictive failure detection
- auto artifact repair
- runtime scaling decisions
- anomaly detection

## 13. Guardian Guarantees

If Guardian is active:
- runtime anomalies detected
- automatic recovery attempted
- platform invariants protected
- system stability maintained

## 14. Relationship to Other Documents

Guardian works with:
- `docs/0LUKA_KERNEL_INVARIANTS.md`
- `docs/0LUKA_STATE_MACHINE_SPEC.md`
- `docs/0LUKA_RUNTIME_VALIDATOR.md`

These define rules and detection.

Guardian provides enforcement and recovery.

Current implementation entrypoint:
- `tools/ops/runtime_guardian.py`

Current proven scope:
- validator-driven monitoring
- guardian action logging
- activity feed emission
- safe non-destructive actions: `none`, `report_only`, `freeze_and_alert`

Not yet proven:
- destructive recovery
- automatic artifact repair
- broad service restart automation

## 15. Runtime Safety Model

The complete safety chain becomes:

```text
Kernel Invariants
        ↓
State Machine
        ↓
Runtime Validator
        ↓
Runtime Guardian
        ↓
Runtime Execution
```

This architecture allows 0luka to function as a self-protecting runtime platform.

## Summary

The Runtime Guardian introduces automatic protection and recovery to the 0luka system.

It transforms the platform from:
- validated runtime

into:
- self-healing runtime platform

capable of detecting, isolating, and recovering from runtime anomalies without operator intervention.
