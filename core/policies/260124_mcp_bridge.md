# ⚖️ 0luka Policy: MCP Bridge Standard (Google Tasks Edition)

**Status:** DRAFT v1.0 | **Authority:** Capability-Centric

## 1. Definition of MCP within 0luka

**Model Context Protocol (MCP)** ถูกนิยามว่าเป็น "Bridge Extension" ภายใน **Layer 2 (Gateway)** เพื่อทำหน้าที่เป็นท่อส่งข้อมูล (Data Pipeline) ระหว่าง Orchestrators และ External Task Managers (เช่น Google Tasks)

## 2. Authorization & Security Gates

* **Encrypted Access:** การเข้าถึง Google Tasks ผ่าน MCP ต้องทำผ่าน OAuth 2.0 ที่ถูกจัดการโดย Gateway (Antigravity) เท่านั้น
* **Verification Requirement:** ข้อมูลที่ดึงมาจาก MCP (Task List) มีสถานะเป็น "External Intent" และต้องถูกแปลงเป็น **Workspace Artifact (`TASKLIST.md`)** ก่อนจะมีการ Execute ใดๆ ในเลเยอร์ 3

## 3. Operational Workflow (Sync Protocol)

1. **Pull Context:** Orchestrator (Gemini/Claude) ใช้ MCP Tool เพื่ออ่านรายการงานจาก Google Tasks
2. **Artifact Generation:** ระบบต้องเขียนรายการงานลงใน Workspace เพื่อสร้าง "หลักฐานท้องถิ่น" (Local Evidence)
3. **Handoff to Executor:** Antigravity Runner อ่านไฟล์ใน Workspace และลงมือทำตามคำสั่ง
4. **Status Callback:** เมื่อจบงาน (Promotion Success) Gateway จะส่งสัญญาณกลับไป Check-off งานใน Google Tasks ผ่าน MCP
