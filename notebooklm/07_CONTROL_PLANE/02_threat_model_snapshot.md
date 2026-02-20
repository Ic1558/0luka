# 0luka Threat Model Snapshot

Version: 2026-02-20  
Scope: Kernel v3 + B2.1 (Append-only Guard v1)  
Mode: Read-Only Analysis  
Status: Informational (Non-Mutating)

---

## 1. Purpose

This document captures the current threat model of the 0luka kernel after Phase A completion.

It defines:
- What is protected
- What is not protected
- Known attack surfaces
- Why current hardening level is sufficient

This document SHALL NOT introduce new invariants.
It SHALL NOT modify kernel behavior.
It is strictly observational.

---

## 2. What Is Protected

### 2.1 Execution Integrity

- Dispatcher runs under launchd supervision.
- Malformed YAML does not crash dispatcher.
- Quarantine path handles invalid inputs.
- Guard violations do not terminate runtime.

Threat mitigated:
- Crash cascade from malformed input.

---

### 2.2 Structural Integrity

- Submit schema enforcement active.
- Activity feed ordering enforced.
- Linter requires `ok=true` and `violations=0` before freeze.

Threat mitigated:
- Invalid TaskSpec injection.
- Structural history corruption.

---

### 2.3 Governance Integrity

- Direct-to-main commits forbidden.
- Mandatory PR path enforced.
- Baseline tag immutability required.
- System Contract centralized in Control Plane.

Threat mitigated:
- Unauthorized kernel mutation.

---

### 2.4 Data Integrity (Append-Only Guard v1)

Guard protects against:

- Feed truncation (`truncate_detected`)
- Last-line rewrite (`rewrite_detected`)
- Silent reorder proxy (hash mismatch)

Violation handling:

- Event not appended
- Violation logged separately
- Runtime remains operational (fail-closed)

Threat mitigated:
- Manual log tampering
- Accidental file overwrite

---

## 3. What Is Not Protected

### 3.1 Deep Historical Rewrite

Guard v1 detects:
- Size reduction
- Last-line hash mismatch

Guard v1 does NOT detect:
- Coordinated rewrite of historical lines
- Followed by consistent last-line reconstruction

Risk:
- Low likelihood (manual only)
- Medium impact

Deferred to:
- Potential B2.2 (hash-chain), not required at present.

---

### 3.2 Coordinated OS-Level Tampering

If attacker:
- Gains shell access
- Modifies both feed and guard state coherently

Guard v1 cannot detect synchronized rewrite.

Out of scope:
- OS privilege escalation
- Root-level compromise

Mitigation layer:
- File permissions
- Operational discipline

---

### 3.3 Git History Manipulation

Kernel does not detect:
- Remote force-push
- History rewrite on origin/main

Mitigation:
- Protected branches
- Governance discipline
- Repository controls

---

### 3.4 Resource Exhaustion

Guard does not limit:
- Feed growth
- Violation log growth

Risk:
- Low (current scale)

---

## 4. Attack Surface Summary

| Surface                     | Type        | Severity | Status       |
|-----------------------------|------------|----------|--------------|
| Malformed Inbox Input       | Accidental | Low      | Mitigated    |
| Manual Feed Edit            | Accidental | Low      | Mitigated    |
| Deep Feed Rewrite           | Intentional| Medium   | Deferred     |
| OS Root Tamper              | Intentional| High     | Out of scope |
| Git Force Push              | Governance | Medium   | Policy-based |

---

## 5. Hardening Sufficiency Assessment

Current threat model assumption:

Primary risk = human error or casual tampering  
Not state-level adversary.

Append-Only Guard v1 sufficiently protects against:
- Accidental edits
- Manual truncation
- Casual rewrite attempts

Hash-chain implementation at this stage would:
- Increase complexity
- Increase operational fragility
- Increase mutation risk

Conclusion:

Guard v1 is appropriate for current system maturity.

---

## 6. Strategic Recommendation

DO NOT implement B2.2 at this time.  
DO NOT modify existing invariants.  
DO NOT mutate kernel behavior.

Proceed to:

Observability Layer (Mission Control, Read-Only).

---

Status: Stable Baseline Confirmed  
Kernel Classification: Execution-Grade Stable
