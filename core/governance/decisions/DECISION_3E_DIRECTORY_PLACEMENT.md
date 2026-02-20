# Decision: PHASE_3E Directory Placement

**Decision ID**: DECISION_3E_DIRECTORY_PLACEMENT
**Author**: CLC
**Date**: 2026-02-12
**Status**: RECOMMENDATION ISSUED
**Scope**: DESIGN ONLY — no implementation, no registry change, no activity fabrication

---

## Executive Summary

PHASE_3E (Cost Router + Budget) was initially placed under `core_brain/agents/`. This decision evaluates whether to keep it there, migrate to `core/`, or use a hybrid approach.

**Recommendation: RECOMMEND KEEP** — remain under `core_brain/agents/`.

The cost router is a **brain-layer advisory classifier**, not a kernel-layer enforcement primitive. Moving it into `core/` would violate the existing constitutional separation between kernel (deterministic pipeline) and brain (intelligence-layer reasoning). The migration cost is non-zero, the governance risk is real (R3 path escalation), and the architectural benefit is nil.

---

## A. Directory Decision

### Current Architecture: Two-Layer Separation

```
core/                          ← KERNEL (R3: hard stop)
  config.py                    ← Path constants
  submit.py                    ← Task submission ABI
  task_dispatcher.py           ← Queue processing
  outbox_writer.py             ← Result persistence
  seal.py                      ← Cryptographic signing
  timeline.py                  ← Event logging
  circuit_breaker.py           ← Failure protection
  schema_registry.py           ← Schema validation
  enforcement.py               ← Policy enforcement
  governance/                  ← Machine-owned registry
    phase_status.yaml          ← Phase verdicts (machine-written)
    tier3_abi.yaml             ← ABI contract (frozen)

core_brain/                    ← BRAIN LAYER (R2: approval lane)
  compiler/                    ← Task compilation
    task_enforcer.py           ← Plan validation
    skill_wiring.py            ← Skill alias resolution
  governance/                  ← Brain-layer policies (human-authored)
    agents.md                  ← Agent roles, complexity rules
    pre_claim_contract.md      ← CLEC risk matrix
    plan_phase_3E_cost_router.md ← 3E architecture plan
  agents/                      ← [PROPOSED] Agent team modules
    cost_router.py             ← Model tier classification
    cost_budget.py             ← Spend tracking
```

### Why This Separation Exists

| Layer | Purpose | Risk Level | Write Policy |
|-------|---------|-----------|-------------|
| `core/` | Deterministic pipeline primitives. If these break, **nothing works**. | R3 (Kernel) | CLC-only, Boss approval required |
| `core_brain/` | Intelligence-layer modules. If these break, **tasks degrade but pipeline survives**. | R2 (Governance) | CLC arch, Gemini impl, approval lane |

The cost router is definitionally brain-layer:
- It classifies tasks using **heuristic rules** (path prefix matching, intent keyword matching)
- Its output is **advisory** (the coordinator acts on it, not the pipeline)
- It has **zero execution power** (cannot submit, cannot write to outbox, cannot sign envelopes)
- If it crashes, the pipeline continues — coordinator falls back to default tier

### Evaluation of Each Option

**Option: `core/agents/`**
- Places an advisory classifier next to `submit.py`, `seal.py`, `circuit_breaker.py`
- These are enforcement primitives. Cost router is not.
- Violates: Constitutional layer separation
- Risk: `core/` is R3. Any change to cost_router.py would require Boss approval per CLEC pre_claim_contract. This is governance overhead for a module that adjusts model selection — not kernel behavior.

**Option: `core/governance/`**
- `core/governance/` currently contains machine-owned artifacts: `phase_status.yaml`, `tier3_abi.yaml`, `decisions/`
- Cost router is executable Python, not a governance artifact
- Violates: Content-type consistency of `core/governance/`

**Option: `core/economic/`**
- New directory under `core/` — still R3
- Creates a precedent for non-kernel code in kernel space
- No existing pattern for this directory
- Violates: Minimal change principle, R3 escalation

**Option: `core_brain/agents/` (current)**
- Adjacent to `core_brain/compiler/` (task_enforcer, skill_wiring)
- Same risk level (R2) as other brain-layer modules
- Same write policy (CLC arch, Gemini impl)
- Import pattern matches: `core_brain.compiler.task_enforcer` → `core_brain.agents.cost_router`
- No new risk escalation
- Aligns with existing `from core.timeline import emit_event` consumption pattern (brain reads kernel, not reverse)

---

## B. Proposed Final Layout (No Migration)

Since recommendation is KEEP, this section shows the **confirmed target layout** under `core_brain/`:

```
repo/
├── core/                                    ← KERNEL (R3, unchanged)
│   ├── config.py                            ← Path constants (add COST_ROUTER_REPORTS)
│   ├── submit.py                            ← ABI: submit_task()
│   ├── outbox_writer.py                     ← ABI: write_result_to_outbox()
│   ├── timeline.py                          ← ABI: emit_event()
│   ├── circuit_breaker.py                   ← ABI: CircuitBreaker
│   ├── seal.py                              ← ABI: sign_envelope()
│   ├── governance/
│   │   ├── phase_status.yaml                ← Machine registry (PHASE_3E: DESIGNED)
│   │   ├── tier3_abi.yaml                   ← ABI contract (frozen)
│   │   └── decisions/
│   │       └── DECISION_3E_DIRECTORY_PLACEMENT.md  ← THIS FILE
│   └── verify/                              ← Test suites
│       └── ... (existing tests)
│
├── core_brain/                              ← BRAIN LAYER (R2)
│   ├── compiler/
│   │   ├── task_enforcer.py                 ← Existing: plan validation
│   │   └── skill_wiring.py                  ← Existing: skill alias resolution
│   ├── governance/
│   │   ├── agents.md                        ← Complexity rules (L0-L3+)
│   │   ├── pre_claim_contract.md            ← Risk matrix (R0-R3)
│   │   └── plan_phase_3E_cost_router.md     ← 3E architecture plan
│   └── agents/                              ← NEW (Phase 3E+)
│       ├── __init__.py
│       ├── cost_router.py                   ← 3-classifier routing engine
│       ├── cost_budget.py                   ← Spend tracking + budget enforcement
│       ├── model_registry.yaml              ← Static model tier declarations
│       ├── agent_config.yaml                ← Per-agent defaults
│       ├── spawner.py                       ← [Future: Phase 3A]
│       ├── coordinator.py                   ← [Future: Phase 3C]
│       ├── file_lock.py                     ← [Future: Phase 3D]
│       └── tests/
│           ├── __init__.py
│           ├── test_cost_router.py
│           └── test_cost_budget.py
│
├── observability/
│   ├── logs/
│   │   └── activity_feed.jsonl              ← Activity chain (unchanged path)
│   └── reports/
│       ├── cost_router/                     ← NEW (created, .gitkeep exists)
│       │   ├── decisions.jsonl              ← [Runtime: append-only audit]
│       │   └── spend_ledger.jsonl           ← [Runtime: append-only spend]
│       └── phase3E/                         ← NEW (created, .gitkeep exists)
│           └── cost_router_proof.json       ← [Runtime: verification evidence]
│
└── docs/
    └── dod/
        └── DOD__PHASE_3E.md                 ← DoD (unchanged path)
```

### What Files Move: NONE

No existing files change location. All new files are created in `core_brain/agents/`.

### What Paths Change: NONE

All paths in `DOD__PHASE_3E.md` and `plan_phase_3E_cost_router.md` remain valid as-is.

### What Imports Change: NONE

Existing imports are unaffected. New imports follow the established pattern:

```python
# cost_router.py consuming kernel ABI (brain → kernel, allowed)
from core.timeline import emit_event
from core.circuit_breaker import CircuitBreaker
from core.config import ROOT, OBSERVABILITY_DIR

# cost_router.py consuming brain-layer governance (brain → brain, allowed)
# (loaded as YAML/MD at design time, not Python import)

# coordinator.py consuming cost_router (brain → brain, allowed)
from core_brain.agents.cost_router import select_model, CostRouter
```

**Forbidden pattern** (kernel → brain): `core/` NEVER imports from `core_brain/`. This is preserved.

### What Evidence Paths Remain Stable

| Evidence Artifact | Path | Layer |
|------------------|------|-------|
| Activity feed | `observability/logs/activity_feed.jsonl` | Observability (unchanged) |
| Decisions log | `observability/reports/cost_router/decisions.jsonl` | Observability (new) |
| Spend ledger | `observability/reports/cost_router/spend_ledger.jsonl` | Observability (new) |
| Phase proof | `observability/reports/phase3E/cost_router_proof.json` | Observability (new) |
| DoD | `docs/dod/DOD__PHASE_3E.md` | Docs (unchanged) |

All evidence paths are under `observability/` — never under `core/` or `core_brain/`. This is correct regardless of where the source code lives.

---

## C. Impact Analysis

### C.1 Activity Feed Path Impact

| Scenario | Impact |
|----------|--------|
| Keep in `core_brain/` | **ZERO**. Activity feed path is `observability/logs/activity_feed.jsonl` per `dod_checker.py` line 168. Source code location is irrelevant to activity feed location. |
| Move to `core/` | **ZERO**. Same reason — activity path is decoupled from source path. |

**Verdict**: No impact either way.

### C.2 Evidence Path Impact

| Scenario | Impact |
|----------|--------|
| Keep in `core_brain/` | **ZERO**. Evidence paths are under `observability/reports/`. Already configured in DoD. |
| Move to `core/` | **ZERO**. Evidence paths don't reference source code location. |

**Verdict**: No impact either way.

### C.3 dod_checker Phase Detection Impact

`dod_checker.py` detects phases by:
1. Reading `docs/dod/DOD__PHASE_*.md` (DoD file)
2. Reading `core/governance/phase_status.yaml` (registry)
3. Reading `observability/logs/activity_feed.jsonl` (activity chain)

None of these reference `core_brain/agents/` or `core/agents/`. Phase detection is **fully decoupled** from source code location.

| Scenario | Impact |
|----------|--------|
| Keep in `core_brain/` | **ZERO**. dod_checker never reads source files for verdict calculation. |
| Move to `core/` | **ZERO**. Same reason. |

**Verdict**: No impact either way.

### C.4 Phase Registry Path References

`phase_status.yaml` contains:
- `evidence_path`: Points to `observability/reports/` — not source code
- `commit_sha`: Git object — not path-dependent
- `requires`: Phase IDs — not paths

| Scenario | Impact |
|----------|--------|
| Keep in `core_brain/` | **ZERO**. Registry doesn't reference source paths. |
| Move to `core/` | **ZERO**. Same reason. |

**Verdict**: No impact either way.

### C.5 Retention Policy Paths

`core/retention.py` manages JSONL rotation. New JSONL files (`decisions.jsonl`, `spend_ledger.jsonl`) are under `observability/reports/cost_router/`. This path must be added to retention config regardless of where source code lives.

| Scenario | Impact |
|----------|--------|
| Keep in `core_brain/` | Need to add `observability/reports/cost_router/*.jsonl` to retention. |
| Move to `core/` | Same. Retention config is the same either way. |

**Verdict**: Identical work required regardless.

### C.6 Future Aggregator v0 Compatibility

A future cross-agent aggregator would read:
- `observability/reports/cost_router/decisions.jsonl` (audit trail)
- `observability/reports/cost_router/spend_ledger.jsonl` (spend data)

These are under `observability/` — stable regardless of source location.

| Scenario | Impact |
|----------|--------|
| Keep in `core_brain/` | Aggregator reads `observability/`. No coupling to source location. |
| Move to `core/` | Same. |

**Verdict**: No impact either way.

---

## D. Decision Matrix

| Criterion | Option 1: Keep `core_brain/` | Option 2: Move to `core/` | Option 3: Hybrid |
|-----------|-----|-----|-----|
| **ABI Safety** | 5/5 — Zero change | 5/5 — Zero change (ABI is path-independent) | 5/5 — Zero change |
| **Enterprise Clarity** | 4/5 — Clear brain/kernel separation | 3/5 — Blurs kernel boundary with advisory code | 3/5 — Splits related modules across layers |
| **Long-term Scalability** | 5/5 — `core_brain/agents/` holds all Tier 3 modules (3A, 3C, 3D) | 3/5 — All Tier 3 would need to be R3, increasing governance burden | 2/5 — Coordinator in one place, router in another |
| **Migration Risk** | 5/5 — Zero (no migration) | 3/5 — Import paths change, test references change, 12+ files affected | 2/5 — Partial migration = worst of both worlds |
| **Strict-mode Risk** | 5/5 — Zero (no dod_checker impact) | 5/5 — Zero (dod_checker is path-independent) | 5/5 — Zero |
| **R3 Escalation** | 5/5 — Stays R2 (appropriate for advisory code) | 2/5 — Becomes R3 (requires Boss approval for every cost_router tweak) | 3/5 — Some files R3, some R2 |
| **Dependency Direction** | 5/5 — Brain → Kernel (correct: brain reads kernel ABI) | 2/5 — Would create kernel-level module that reads brain-layer governance docs | 3/5 — Mixed |
| **Total** | **34/35** | **23/35** | **23/35** |

---

## E. Risk Assessment

### Moving to `core/` Introduces These Risks

1. **R3 Path Escalation**: Per CLEC `pre_claim_contract.md`, any file under `core/` is R3 (Kernel). Changes to `cost_router.py` would require Boss approval for what is fundamentally a classifier tuning operation (adjusting which keywords map to which complexity level). This is governance overhead without security benefit.

2. **Dependency Inversion**: Cost router reads `agents.md` (L0-L3+ rules) and `pre_claim_contract.md` (R0-R3 matrix). These are in `core_brain/governance/`. Placing the consumer in `core/` while its configuration lives in `core_brain/` creates a kernel → brain dependency. The established rule is brain → kernel only, never the reverse.

3. **Precedent Contamination**: If cost_router goes into `core/`, then spawner, coordinator, and file_lock (Phases 3A, 3C, 3D) must also go into `core/` for consistency. This adds 4+ new Python modules to the kernel — modules that are advisory, not enforcement. The kernel becomes bloated with intelligence-layer concerns.

4. **Test Suite Coupling**: 12 existing test files reference `core_brain.compiler.*` via `importlib.import_module()`. Adding `core_brain.agents.*` tests follows the same pattern. Moving to `core/agents/` would create `core.agents.*` imports — mixing test patterns and making it harder to distinguish kernel tests from brain tests.

### Keeping in `core_brain/` Has Zero Identified Risks

- ABI is path-independent (frozen in `tier3_abi.yaml`)
- Evidence is under `observability/` (decoupled)
- Activity feed is under `observability/` (decoupled)
- dod_checker is path-independent (reads DoD files, registry, activity — not source)
- Import direction is correct (brain → kernel)
- Risk level is appropriate (R2 for advisory code)

---

## Final Recommendation

### **RECOMMEND KEEP**

PHASE_3E remains under `core_brain/agents/`.

**Rationale in one sentence**: The cost router is a brain-layer advisory classifier that reads kernel ABI but has zero execution power — placing it in the kernel would elevate its governance risk (R2→R3) without any architectural benefit, since all evidence paths, activity feeds, and dod_checker detection are fully decoupled from source code location.

**No files move. No paths change. No imports change. No registry modification.**

The current plan (`plan_phase_3E_cost_router.md`) and DoD (`DOD__PHASE_3E.md`) are already correct.

---

**Governance Lock**: This decision is recorded in `core/governance/decisions/`. Any reversal requires Boss approval.
