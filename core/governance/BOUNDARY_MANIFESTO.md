# 0luka Boundary Manifesto
---
version: 1.0
status: ACTIVE
type: HARD CONSTRAINT
---

## 1. Core Identity
**0luka is:** Control & Governance Orchestrator | Deterministic task router | Audit trail keeper

**0luka is NOT:** CAD/BIM engine | Geometry processor | Image-first creative system

## 2. Hard Boundaries

### 2.1 Geometry Boundary
| Forbidden | Reason |
|-----------|--------|
| LLM creates/modifies geometry | Geometry requires determinism; LLM is probabilistic |
| LLM interprets scale from image | Data loss is unrecoverable |
| PDF -> image -> LLM -> 3D | Wrong abstraction |

**Canonical Truth:** `PDF (vector) -> AutoCAD/SketchUp -> 3D` — LLM is never in this chain.

### 2.2 Execution Boundary
| Actor | Can Execute? |
|-------|--------------|
| Claude/LLM | NO |
| 0luka | Only via: preview -> confirm -> drop -> agent |

### 2.3 Creative/AEC Boundary
| Claude CAN | Claude CANNOT |
|------------|---------------|
| Review brief/intent | Judge design correctness |
| Check requirement completeness | Be source of measurement |
| Audit decisions | Generate geometry |

## 3. Lane Separation
| Lane | Owner | Truth Source |
|------|-------|--------------|
| Deterministic | Human + CAD | PDF, AutoCAD, SketchUp |
| Semantic | Claude | Language, intent, audit |

**Rule:** Lanes do not cross.

## 4. Enforcement
Any proposal touching these boundaries must answer:
> "Where is the determinism?"

If unanswerable -> **proposal is invalid**.

## 5. Status
| Component | State |
|-----------|-------|
| NLP Control Plane | LOCKED |
| Design Lane (LLM-first) | DECOMMISSIONED |
| Claude Role | CONFIRMED & LIMITED |

— Governance Lock

---
**DO NOT EDIT WITHOUT GOVERNANCE APPROVAL**
