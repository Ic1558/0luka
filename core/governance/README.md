# Governance — Canonical Documents
---
version: 1.0
status: AUTHORITATIVE
---

## Document Hierarchy

| Document | Type | Purpose |
|----------|------|---------|
| `soul.md` | Identity | Who 0luka is, what it values |
| `BOUNDARY_MANIFESTO.md` | Hard Constraint | What 0luka/LLM cannot do |
| `prps.md` | Policy | Project registration & structure |
| `router.md` | Protocol | Intent routing rules |
| `ontology.yaml` | Schema | Entity definitions & invariants |

## Reading Order

1. **soul.md** — Start here (identity anchor)
2. **BOUNDARY_MANIFESTO.md** — Hard limits
3. **prps.md** — Structural rules
4. **router.md** — Routing protocol
5. **ontology.yaml** — Technical schema

## Conflict Resolution

When documents conflict:
```
soul.md < BOUNDARY_MANIFESTO.md
```
Hard constraints always win over identity statements.

## Edit Policy

All documents in this directory are **governance-locked**.
Changes require explicit Boss approval.

---
**DO NOT EDIT WITHOUT GOVERNANCE APPROVAL**
