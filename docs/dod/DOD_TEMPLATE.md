<!--
DoD Template v1.0
Usage: Copy to docs/dod/DOD__<PHASE_ID>.md and fill details.
-->
# DoD Template Standard

## Metadata & Revision History
- **Version**: v1.2
- **Edited By**: GMX (Agentic AI Assistant)
- **Date**: 2026-02-12
- **Reason**: Add proof mode (synthetic/operational) expectations.

# DoD — <PHASE_OR_TASK_ID>

## 0. Metadata (MANDATORY)
- **Phase / Task ID**:
- **Owner (Actor)**:
- **Gate**:
- **Related SOT Section**:
- **Target Status**: DESIGNED → PARTIAL → PROVEN
- **Commit SHA**:
- **Date**:

---

## 1. Code State (Static Integrity)
- [ ] Feature implemented (commit referenced)
- [ ] No hard paths (grep verified)
- [ ] Follows `ref://` resolution
- [ ] Lint passes
- [ ] Type-check passes (if applicable)
- [ ] No decommissioned file modified
- [ ] No test bypass added (no silent skips)

---

## 2. Runtime State (Process Truth)
*(Skip if not a daemon/service)*
- [ ] Service runs under launchd/systemd
- [ ] PID confirmed alive
- [ ] Survives restart/reboot
- [ ] No infinite error loops
- [ ] Heartbeat present (if daemon)
- [ ] Logs bounded (rotation or bounded file)

---

## 3. Functional Validation (Deterministic Behavior)
- [ ] Valid input processed correctly
- [ ] Invalid input rejected correctly
- [ ] No silent failure (error must surface)
- [ ] Idempotent re-run consistent (if applicable)
- [ ] No side-effect outside declared scope

---

## 4. Evidence (Fail-Closed Core)
- [ ] JSONL log produced (path recorded)
- [ ] Provenance recorded (path recorded)
- [ ] Execution hash stored (if execution involved)
- [ ] Activity event: `started`
- [ ] Activity event: `completed`
- [ ] Activity event: `verified`
- [ ] Error logs clean in last 200 lines (command recorded)

---

## 5. Negative Testing (Abuse Resistance)
- [ ] Malformed input test
- [ ] Permission violation test
- [ ] Schema violation test
- [ ] Unexpected exception test
- [ ] Boundary violation attempt (if security-sensitive)

---

## 6. Documentation & Governance Sync
- [ ] PPR updated
- [ ] Unlock map updated
- [ ] Gate status updated
- [ ] Status badge aligned with Activity Feed
- [ ] SOT updated (only if architecture changed)

---

## 7. Gate Check (Non-negotiable)
- [ ] Required prior Phase(s) **PROVEN**
- [ ] No open **BLOCKED** dependency
- [ ] Auto-Checker result = **PROVEN**

---

## Verdict (Strict)
- **DESIGNED** / **PARTIAL** / **PROVEN**

### Notes / Links (Evidence pointers)
- **Proof Mode**: `operational` (runtime_auto) | `synthetic` (manual/tool)
- **Evidence artifact**: `observability/reports/dod_checker/...`
- **Activity Feed**: `observability/logs/activity_feed.jsonl`
- **Verifier Mode**: `operational_proof` | `synthetic_proof`
