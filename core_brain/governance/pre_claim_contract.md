# 📜 Closed-Loop Engineering Contract (CLEC) v1.0
**Status**: [ACTIVE] [SOT] | **Branding**: 0luka | **Scope**: Code & Maintenance

## 1. 🎯 Purpose & Iron Rule
งานจะถือว่า **"Done"** ได้ก็ต่อเมื่อผ่าน "วงจรปิด" (Closed-Loop) ครบ 5 ขั้นตอน:
1. **Plan**: เจตนาชัด (Intent) ใน TaskSpec/PatchPlan
2. **Apply**: แก้ไขไฟล์จริงแบบ Atomic
3. **Validate**: ตรวจสอบด้วยเครื่องยนต์ (Tests/Lint/Build)
4. **Evidence**: บันทึกหลักฐาน (Hash/Diff/Log) ลงใน `evidence.v1`
5. **Trace**: ตรวจย้อนกลับไปหาต้นทาง (Prompt/Author) ได้

## 2. 🎭 Roles (0luka Actors)
- **Proposer (Liam/GMX)**: ร่างแผนและ Patch (ไม่มีสิทธิ์รันเอง)
- **Executor (Lisa)**: Apply งาน + รัน Validation + ออก Evidence
- **Approver (Boss)**: ตัดสินใจใน Approval Lane + ฉีด Audit Metadata

## 3. 🛡️ Pre-Claim Gates (The 5 Fence-posts)
ก่อน Lisa จะ Claim งาน ต้องผ่านด่านตรวจอัตโนมัติ:
- **G1 [Workspace]**: ต้องอยู่ใน `~/0luka` เท่านั้น
- **G2 [Risk/Lane]**: ตรวจ Path R0-R3 และ Lane (กัน Bypass)
- **G3 [Schema]**: ต้องผ่าน `clec_v1.yaml` Validation
- **G4 [No Secrets]**: แจ้งเตือน/บล็อก หากพบ Secret หรือ .env รั่วไหล
- **G5 [Loop Defined]**: ต้องมี Verification Check อย่างน้อย 1 อย่าง (ถ้าไม่มี = REJECT)

## 4. 📊 Risk Matrix & Routing
| Level | Name | Paths | Lane | Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **R0/R1** | Normal | `modules/`, `reports/`, `tools/`, `docs/` | **FAST** | Auto-Execute |
| **R2** | Governance | `interface/schemas/`, `governance/`, `luka.md` | **APPROVAL** | Hold for Boss |
| **R3** | Kernel/Core | `core/`, `runtime/`, `.env*` | **REJECT** | Hard stop |

## 5. 📑 Evidence Contract (evidence.v1)
ทุกงานต้องทิ้งไฟล์ `EVID-<task_id>-<ts>.json` ที่มี:
- **artifacts[]**: `sha256_before` / `sha256_after` ของทุกไฟล์ที่แตะ
- **verification**: ผลลัพธ์ของ Loop (pass/fail)
- **audit**: (ถ้ามี) ใครเป็นคน Approve + Source Hash

## 6. 🚫 Non-Goals
- ไม่ทำงาน Creative Writing (เน้นหลักฐานเชิงกล)
- ไม่ "เดา" ผลลัพธ์ (ไม่มี Verification = ไม่จบงาน)
- ไม่ทำงานข้ามเครื่อง (Single-host v1.0)
- ไม่จัดการ Lifecycle ของ Process/Launchd

## 7. 💡 Mental Model
> **"Prompt/Intent สำคัญกว่าโค้ดดิบ — หลักฐานสำคัญกว่าคำพูด"**
