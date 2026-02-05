# OPAL v2 ROADMAP — What Changes, What Must Not

**Status:** Non-Authoritative (Intent/Plan)
**Rule:** This document does NOT override the Kernel Constitution.
v2 is adding capability without destroying the law.

---

## 🔒 Things That MUST Stay
- Kernel-as-ABI
- Byte-identical OpenAPI
- Job lifecycle determinism
- Engine-agnostic worker
- Provenance requirement

---

## 🧩 v2 Focus Areas

### v2.0 — Multi-Worker / Multi-Host
- Worker registration
- Heartbeat
- Distributed queue
- Host-aware scheduling
- *No change to Job ABI*

### v2.1 — Artifact Backend
- Pluggable storage (FS / S3 / R2)
- Signed artifact URLs
- Retention policies per job class

### v2.2 — Policy Layer
- Job priority
- Quotas
- User/Operator identity
- Audit trails

### v2.3 — Declarative Pipelines
- Job → Pipeline
- DAG execution
- Fan-out / Fan-in

---

## 🚫 Explicit Non-Goals for v2
- **No** "smart UI behavior"
- **No** engine-specific optimization in kernel
- **No** silent schema evolution
