# 0luka — Gateway Architecture & Autonomous AI Labor Management (v1)
Date: 2026-01-23T16:20:28+0700

## Executive Summary
0luka ถูกออกแบบเพื่อยกระดับการพัฒนาแบบ “AI-Generated” ให้ปลอดภัยและตรวจสอบได้ โดยยึดแนวคิด **Gateway Architecture**: มนุษย์สั่งผ่านจุดเดียว (Single Entry Point) และให้ AI Agents เป็นแรงงานในพื้นที่จำกัด (Sandbox) ด้วยหลักฐานเป็น “Artifacts” แทนการเชื่อ log ยาวๆ

หัวใจคือการป้องกัน 3 เรื่อง:
- **Code Integrity**: ห้ามแก้ Kernel ตรง
- **Security**: secrets ไม่เข้ากิต + policy gate
- **Context Consistency**: กันงานชน/บริบทล้าด้วย pull/rebase + hook

---

## 1) Architecture Definition (3 Layers)
ระบบแบ่งเป็น 3 เลเยอร์เพื่อกำหนด “ขอบเขตอำนาจ” ชัดเจน

### Layer 1 — Kernel
- สิ่งที่ถือว่า “จริงหนึ่งเดียว” (Source of Truth) และต้อง deploy ได้
- ตัวแทนใน repo: โฟลเดอร์ `core/`
- กฎเหล็ก: **ห้ามแก้ไขโดยตรง** (Direct Modification Prohibited)  
  การเปลี่ยน Kernel ต้องเกิดผ่าน “Promotion” เท่านั้น

### Layer 2 — Gateway
- จุดควบคุม/สั่งงานของมนุษย์ (Architect / Orchestrator)
- Default Gateway: **Google Antigravity**
- สื่อสารด้วย Artifacts: plan/checklist/diff/patch ไม่ใช่ raw chat

### Layer 3 — Workers
- พื้นที่ทำงานแยกเป็นงานๆ (Isolated Workspaces) ใต้ `workspaces/`
- Agent เขียน/แก้เฉพาะใน workspace แล้ว “ส่งมอบ” เป็น artifact เพื่อ promote

---

## 2) Data Flow (Unidirectional for Code)
1) **Sync**: Gateway/Kernel ดึงของล่าสุด (pull --rebase)
2) **Fork**: สร้าง workspace จาก Kernel
3) **Mutate**: Agent แก้โค้ดใน workspace
4) **Verify**: สร้าง artifact (diff/patch/summary) + PRP checks
5) **Promote**: มนุษย์อนุมัติ → นำเข้าที่ Kernel
6) **Push**: Kernel push กลับ upstream

---

## 3) Enforcement (Git Hooks Strategy)
ต้องมี “ภูมิคุ้มกัน” กันลืม/กันพัง

### pre-commit
- กันการ commit ที่ไปแตะ `core/` โดยตรง
- ยกเว้นเฉพาะโหมด promotion ที่สคริปต์ตั้ง env ให้

### pre-push
- บังคับ sync ก่อน push
- ถ้า local “behind origin” → ปฏิเสธ push และบังคับให้ pull --rebase

---

## 4) Workspace Automation
สคริปต์มาตรฐาน:
- `.0luka/scripts/new_workspace.zsh`  
  สร้าง workspace พร้อม manifest (task/model/trace/base_commit) และ inject rules
- `.0luka/scripts/promote_artifact.zsh`  
  ทำ promotion แบบมีหลักฐาน (artifact) + PRP gate ก่อน commit/push

---

## 5) Model Routing (Gemini CLI / Claude Code)
**No model is mandatory. Routing is a suggestion, not an enforcement.**

เลือกใช้โมเดลตาม “ประเภทงาน” และ “ความเร็ว/ความเสี่ยง” ไม่ต้องล็อคว่าเริ่มด้วยตัวไหน

- **Claude / Opencode / Codex (Strategist / Senior)**: planning, refactor โครงสร้าง, audit/review, root-cause
- **Gemini CLI (Tactician / Fast Worker)**: boilerplate, file ops เยอะๆ, test/doc, run scripts

Recommended routing (optional):
1) ใครก็ได้วาง blueprint/plan (Claude/Gemini/Codex/Opencode) ตามความเหมาะสมของงาน
2) ใครก็ได้ลงมือใน workspace (เน้นเร็ว/ไฟล์เยอะ → Gemini มักเหมาะ)
3) ใครก็ได้ audit ก่อน promote (เน้นความเสี่ยง/ตรรกะ → Claude มักเหมาะ)
## 6) Directory Structure (as enforced)
- `core/` : Kernel (Protected)
- `workspaces/` : Ephemeral work areas (ignored / disposable)
- `artifacts/` : Pending + archive evidence (patches, summaries)
- `prps/` : HARD gates (Definition of Done)
- `catalog/rules/` : “กฎหมาย” ที่ inject ให้ agent เห็น

---

## 7) Multi-device Rules (2 machines)
- ก่อนเริ่มงานบนเครื่องไหน: `git pull --rebase`
- หลังทำเสร็จ: `git push`
- ห้ามทำงานพร้อมกัน 2 เครื่องโดยไม่ pull/push (จะชน)

ระบบจะ “บังคับ” ผ่าน pre-push hook + (แนะนำ) alias/gsync + gpush

