# 0luka: Governance-as-an-Interface
**Concept**: 0luka คือระบบทำงานอัตโนมัติที่ "ไม่เชื่อ AI โดยอัตโนมัติ" แต่เชื่อ กฎ + หลักฐาน + ตัวตน

## 🧠 Core Structure (Governance v2.0)
The system is divided into 5 specialized personas, each with strict **Identity Invariants** and **Separation of Concerns**.

1.  **[GMX] (The Sovereign)**:
    -   Role: Policy, Approval, Strategy Oversight.
    -   Power: Determines *WHAT* we do.
2.  **[Liam] (The Architect)**:
    -   Role: Reasoning, Planning, Spec Design (TaskSpec v2).
    -   Power: Defines *HOW* (conceptually).
3.  **[Lisa] (The Executor)**:
    -   Role: Deterministic Execution, Implementation.
    -   Power: *DOES* the work (No reasoning involved).
4.  **[Vera] (The Validator)**:
    -   Role: Forensic Audit, Verdicts.
    -   Power: *JUDGES* the work (Read-only).
5.  **[Rio] (The Explorer)**:
    -   Role: R&D, Sandbox Experiments.
    -   Power: *PROPOSES* new ideas (Sandboxed).

## 🚦 Lane Logic
- **FAST** (Low Risk): งานเอกสาร, modules, ไม่แตะ Core system. -> **Lisa รันเองได้เลย**
- **APPROVAL** (High Risk): แตะ Core, Governance, Tools. -> **ต้องค้าง Pending รอ Boss อนุมัติ**
- **REJECTED**: ผิด Schema, มี Secret, พยายาม Bypass, Path Escape.

## 🔄 The Forensic Loop
1. **Inbox**: รับ TaskSpec (`clec_v1.yaml`)
2. **Pre-Flight**: ตรวจสอบความพร้อม (SOT Fresh, Pending Empty, ID Match, Env Safe)
3. **Validation**: ตรวจสอบสัญญาว่าถูกต้องตาม Schema
4. **Classify**: จัดลำดับความเสี่ยง (R0-R3) และ Lane
5. **Verify**: ตรวจสอบเงื่อนไขก่อนทำ (Pre-checks without side effects)
6. **Execute**: ทำงานจริงแบบ Atomic
7. **Evidence**: บันทึกหลักฐาน Forensic (Git Hash, SOT Ref, Stdout/Stderr, Artifact SHA256)
8. **Codex**: ตรวจสอบหลักฐานสุดท้ายก่อนประทับตรา DONE

## 🛡️ Why 0luka?
- **Silence**: ระบบเงียบเมื่อทุกอย่างถูกต้อง
- **Alarm**: ระบบดังทันทีเมื่อมีอะไรผิด (Fail-Closed)
- **Traceability**: ย้อนดูหลักฐานได้ทุก Trace แม้ผ่านไปนาน

> "0luka = ระบบที่เงียบเมื่อทุกอย่างถูกต้อง และดังทันทีเมื่อมีอะไรผิด"

### 4. Emergency Bypass Policy (v1.0)
**"Breakglass with Forensic Auditing"** - Designed for Operational Deadlocks only.

*   **Strict Scope**:
    *   **Allowed Host**: `icmini` only (Hard Deny on MBP/others).
    *   **Allowed Actor**: `[GMX]` only (Liam/Lisa/Codex Denied).
    *   **Token**: Single-Shot (One-time use, Replay Protected).
*   **Permitted Bypasses**:
    *   SOT Stale Checks (e.g. inability to update SOT due to outage).
    *   Pending Queue Guard (e.g. queue stuck).
*   **Strictly FORBIDDEN (No Override)**:
    *   Path Sandbox (`safe_path`).
    *   Command Whitelist.
    *   Schema Validation.
    *   Identity Check.
    *   R2/R3 Secret Scanning (Fail-Closed).
*   **Audit Trail**:
    *   All attempts logged to `gate_emergency.jsonl` (Immutable).
    *   Result Codes: `approved`, `denied_host`, `denied_actor`, `replay_detected`, `missing_fields`.
