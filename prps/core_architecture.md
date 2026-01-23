# PRP: Core Architecture Standards (Phase 1)

## 1. Root-Level Integrity [HARD CONTRACT]
- **Allowed List:** เฉพาะ `core/`, `.0luka/`, `workspaces/`, `artifacts/`, `prps/`, `catalog/`, `.gitignore`, และ `architecture.md` เท่านั้นที่ได้รับอนุญาต
- **Quarantine Policy:** ไฟล์/โฟลเดอร์อื่นนอกเหนือจากนี้ต้องถูกกักกันทันที

## 2. Kernel Modification Rules
- **Direct Access:** ห้ามแก้ไขโฟลเดอร์ `core/` โดยตรง
- **Promotion Only:** การนำโค้ดเข้าสู่ Kernel ต้องใช้ `promote_artifact.zsh` และผ่านการตรวจสอบ Metadata (644 permission) เท่านั้น

## 3. Validation Logic
- **Bypass Hook:** อนุญาตให้ข้าม Hook ได้เฉพาะเมื่อตั้งค่า `OLUKA_PROMOTION_MODE=1`
- **Artifact Requirement:** ห้าม Promote หากไม่มีไฟล์ Patch หรือ Evidence Log กำกับ
