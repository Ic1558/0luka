# PRP: core_architecture (HARD GATE)
Date: 2026-01-23T16:20:28+0700

เป้าหมาย: ให้ 0luka มีโครงสร้างและ guardrails ขั้นต่ำที่ “กันเจ๊ง” ได้จริง

## PASS/FAIL Checks
### A) Constitution
- [ ] มี `architecture.md` (อธิบาย 3-layer + flow + hooks + workspace/promotion)
- [ ] ยืนยัน Layer 1 = `core/` protected (ห้ามแก้ตรง)
- [ ] ยืนยัน Agent ทำงานผ่าน `workspaces/` และส่งมอบเป็น `artifacts/`

### B) Hooks Enforcement
- [ ] มี `.0luka/hooks/pre-commit` และติดตั้งลง `.git/hooks/pre-commit`
- [ ] มี `.0luka/hooks/pre-push` และติดตั้งลง `.git/hooks/pre-push`
- [ ] pre-commit บล็อกการ commit ไฟล์ใต้ `core/` ถ้าไม่ได้อยู่ใน promotion mode
- [ ] pre-push บล็อกการ push ถ้า local behind origin (ต้อง pull --rebase ก่อน)

### C) Automation Scripts
- [ ] มี `.0luka/scripts/install_hooks.zsh`
- [ ] มี `.0luka/scripts/new_workspace.zsh`
- [ ] มี `.0luka/scripts/promote_artifact.zsh`
- [ ] new_workspace สร้าง manifest ที่มี: task, model, trace_id, base_commit, created_at
- [ ] promote ทำ evidence artifact (patch/diff) และ commit แบบมี metadata

### D) Safety
- [ ] `workspaces/` ถูก ignore ใน git (หรืออย่างน้อยไม่มีของสำคัญถูก commit)
- [ ] secrets อยู่ใน `vault/` หรือ `.env` และถูก ignore

## FAIL Conditions
- แก้ `core/` แล้ว commit ได้โดยไม่ผ่าน promotion mode
- push ได้ทั้งๆ ที่ repo ตามหลัง origin
- promote ไม่มี artifact/evidence

## 5) Model Routing (Gemini CLI / Claude Code)
**No model is mandatory. Routing is a suggestion, not an enforcement.**

เลือกใช้โมเดลตาม “ประเภทงาน” และ “ความเร็ว/ความเสี่ยง” ไม่ต้องล็อคว่าเริ่มด้วยตัวไหน

- **Claude / Opencode / Codex (Strategist / Senior)**: planning, refactor โครงสร้าง, audit/review, root-cause
- **Gemini CLI (Tactician / Fast Worker)**: boilerplate, file ops เยอะๆ, test/doc, run scripts

Recommended routing (optional):
1) ใครก็ได้วาง blueprint/plan (Claude/Gemini/Codex/Opencode) ตามความเหมาะสมของงาน
2) ใครก็ได้ลงมือใน workspace (เน้นเร็ว/ไฟล์เยอะ → Gemini มักเหมาะ)
3) ใครก็ได้ audit ก่อน promote (เน้นความเสี่ยง/ตรรกะ → Claude มักเหมาะ)

