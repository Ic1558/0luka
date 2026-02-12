# DoD — PHASE_3E

## Metadata & Revision History
- **Version**: v1.2
- **Edited By**: CLC
- **Date**: 2026-02-12
- **Reason**: v1.2 — Audit hardening: correct verdict semantics, remove runnable code, add evidence integrity rule.
- **v1.1**: Clarify activity chain ownership, migration scope (2026-02-12).
- **v1.0**: Initial DoD creation (2026-02-12).

## 0. Metadata (MANDATORY)
- **Phase / Task ID**: PHASE_3E
- **Owner (Actor)**: ops-governance
- **Gate**: G1
- **Related SOT Section**: §Tier3.Phase3E
- **Target Status**: DESIGNED → PARTIAL → PROVEN
- **Commit SHA**: 0fbb74ff974b8effb8b54c93c32c06b40ac5a650
- **Evidence Path**: observability/reports/agents/phase_3e_cost_router_proof.json
- **Proof Mode**: operational
- **Date**: 2026-02-12
- **Source Location**: `core_brain/agents/` *(no migration to `core/` — see DECISION_3E_DIRECTORY_PLACEMENT)*

---

## 1. Code State (Static Integrity)
- [ ] Feature implemented (commit referenced)
- [ ] No hard paths (grep verified: no `/Users/` in any 3E file)
- [ ] No decommissioned file modified
- [ ] No test bypass added
- [ ] All imports resolve (`cost_router.py`, `cost_budget.py`)
- [ ] `model_registry.yaml` valid YAML, parseable
- [ ] `agent_config.yaml` valid YAML, parseable

---

## 2. Runtime State (Process Truth)
- [ ] `cost_router.select_model(task)` returns without network I/O
- [ ] `cost_budget.check_budget()` reads local ledger only
- [ ] No process spawned, no daemon started

---

## 3. Functional Validation (Deterministic Behavior)
- [ ] **Classifier 1 (Path Risk)**: R3 path → T0, R2 path → T0, R1 path → T2, R0 path → T3
- [ ] **Classifier 2 (Complexity)**: L3+ → T0, L2 → T1, L1 → T2, L0 → T3
- [ ] **Classifier 3 (Governance)**: Any governance pattern match → T0 override
- [ ] **Composition**: Higher floor wins (max of risk floor, complexity floor)
- [ ] **Determinism**: Same input → same tier (replay test, N=100)
- [ ] **Budget allow**: Within limits → `{allowed: True}`
- [ ] **Budget deny**: Over daily limit → `{allowed: False, reason: "daily_budget_exceeded"}`
- [ ] **Budget deny**: Ledger I/O failure → `{allowed: False, reason: "ledger_read_failure"}`
- [ ] **Budget T0 cap**: T0 daily call count exceeded → `{allowed: False, reason: "t0_daily_limit"}`
- [ ] **Decision logged**: Every `select_model()` call → 1 line in `decisions.jsonl`
- [ ] **Spend recorded**: Every `record_spend()` call → 1 line in `spend_ledger.jsonl`

---

## 4. Evidence (Fail-Closed Core)
- [ ] Activity event: `started`
- [ ] Activity event: `completed`
- [ ] Activity event: `verified`

### Activity Chain Ownership
Activity events for PHASE_3E are emitted by the **verification/test harness**, NOT by
`cost_router.py` or `cost_budget.py` themselves. The router and budget modules are pure
classifiers with no self-proving capability. The activity chain proves that the
**verification loop ran and passed**, not that a routing decision happened.

Sequence:
1. Test harness emits `started` to `activity_feed.jsonl` (with `phase_id: PHASE_3E`)
2. Test harness runs all assertions against `cost_router` and `cost_budget`
3. Test harness writes `cost_router_proof.json` to `observability/reports/phase3E/`
4. Test harness emits `completed` to `activity_feed.jsonl`
5. `dod_checker --phase PHASE_3E` verifies chain + evidence → `verified` emitted only after validation

### Evidence Integrity Rule (Fail-Closed)

> PHASE_3E remains DESIGNED until a real implementation commit replaces TODO_SHA.
> No synthetic, placeholder, or fabricated SHA is permitted to advance verdict state.
> No activity chain may be emitted until implementation code exists and tests pass.

### Notes / Links (Evidence pointers)
- **Architecture Plan**: `core_brain/governance/plan_phase_3E_cost_router.md`
- **Cost Router**: `core_brain/agents/cost_router.py`
- **Cost Budget**: `core_brain/agents/cost_budget.py`
- **Model Registry**: `core_brain/agents/model_registry.yaml`
- **Agent Config**: `core_brain/agents/agent_config.yaml`
- **Test Suite (Router)**: `core_brain/agents/tests/test_cost_router.py`
- **Test Suite (Budget)**: `core_brain/agents/tests/test_cost_budget.py`
- **Decisions Log**: `observability/reports/cost_router/decisions.jsonl`
- **Spend Ledger**: `observability/reports/cost_router/spend_ledger.jsonl`
- **Proof Artifact**: `observability/reports/agents/phase_3e_cost_router_proof.json`
- **Activity Chain**: `observability/logs/activity_feed.jsonl` (phase_id=PHASE_3E)
- **Verification Commands**:
  - `python3 -m pytest core_brain/agents/tests/test_cost_router.py -v`
  - `python3 -m pytest core_brain/agents/tests/test_cost_budget.py -v`
  - `LUKA_REQUIRE_OPERATIONAL_PROOF=1 python3 tools/ops/dod_checker.py --phase PHASE_3E --json`
  - `python3 tools/ops/dod_checker.py --phase PHASE_3E --json`

### Strict Mode Requirements
- `LUKA_REQUIRE_OPERATIONAL_PROOF=1` → strict mode active
- `commit_sha` must be reachable via `git cat-file -t <sha>`
- `synthetic_detected` must be `false`
- `taxonomy_ok` must be `true` (all 7 keys present per event)
- `evidence_path` (`observability/reports/agents/phase_3e_cost_router_proof.json`) must exist and be readable
- `proof_mode` must be `operational` (not `synthetic`)

### Activity Taxonomy Specification (per event)

Each event appended to `activity_feed.jsonl` must contain all 7 `REQUIRED_TAXONOMY_KEYS`:

| Key | Value | Notes |
|-----|-------|-------|
| `action` | `started` / `completed` / `verified` | One of the three chain events |
| `phase_id` | `PHASE_3E` | Must match this phase exactly |
| `emit_mode` | `runtime_auto` | Must NOT be `synthetic` |
| `verifier_mode` | `operational_proof` | Must NOT be `synthetic` |
| `tool` | `cost_router` | Identifies the verification subject |
| `run_id` | UUID4 hex (32 chars) | Must be consistent across all 3 events in one run |
| `ts_epoch_ms` | Integer (milliseconds since epoch) | Monotonically increasing across the chain |
| `ts_utc` | ISO8601 string | Human-readable timestamp |

---

## 5. Negative Testing (Abuse Resistance)
- [ ] Missing `model_registry.yaml` → `FileNotFoundError` on init
- [ ] Empty tier in registry → `ValueError("no_models_in_tier:...")` on `_pick_model()`
- [ ] Corrupted `spend_ledger.jsonl` → `check_budget()` returns `{allowed: False}`
- [ ] Unknown risk level (path matches no rule) → defaults to R0 (lowest restriction)
- [ ] Governance pattern on non-governance file → no false positive (exact prefix match)
- [ ] Timeline `emit_event()` failure → non-fatal, routing still succeeds
- [ ] `decisions.jsonl` write failure → fatal, routing aborts (audit trail is non-negotiable)

---

## 6. Regression Protection
- [ ] No modification to `core/` kernel files
- [ ] No modification to `tools/ops/dod_checker.py`
- [ ] No modification to `core/governance/phase_status.yaml` (except adding PHASE_3E entry)
- [ ] Existing dod_checker tests still pass
- [ ] Existing health.py --full still passes

---

## 7. Gate Check (Non-negotiable)
- [ ] Requires: PHASE_1B (schema validation for task dicts)
- [ ] Requires: PHASE_2 (evidence chain infrastructure)
- [ ] Requires: PHASE_8 (dispatcher — shared queue, ABI baseline)
- [ ] Requires: PHASE_10 (Sentry — output quality gate referenced by escalation logic)
- [ ] Requires: PHASE_15_4 (skill aliases — referenced in governance patterns)
- [ ] Requires: PHASE_OPS (seal + timeline + circuit_breaker — ABI consumed)
- [ ] All 6 prerequisites must be PROVEN (dod_checker exit 0)
- [ ] Auto-Checker result = **PROVEN**

---

## Verdict
- **DESIGNED**

### Verdict Progression Rules

PHASE_3E follows a strict three-stage progression:

| Stage | Condition | Expected Checker Exit |
|-------|-----------|----------------------|
| **DESIGNED** | `commit_sha == TODO_SHA`, no implementation, no activity chain | exit 3 |
| **PARTIAL** | Real reachable 40-hex `commit_sha` exists, but activity chain and/or evidence is incomplete | exit 2 |
| **PROVEN** | Reachable commit + complete activity chain (started→completed→verified) + evidence artifact exists + taxonomy_ok + operational proof_mode | exit 0 |

**Fail-closed rule**: No implementation commit → no escalation beyond DESIGNED.
Well-formed DoD metadata alone does NOT upgrade verdict. A real commit is the first gate.

**Note on current checker behavior**: `dod_checker.py` currently computes PARTIAL (exit 2) for
PHASE_3E because it finds a well-formed DoD file with parseable metadata. This is a known
behavioral artifact of the checker's scoring logic — the governance truth is DESIGNED.
The checker logic is NOT modified; this discrepancy is documented, not suppressed.

### Exit Code Expectations
- `dod_checker --phase PHASE_3E`: exit 0 = PROVEN, exit 2 = PARTIAL, exit 3 = DESIGNED
- `dod_checker --phase PHASE_3E --update-status-phase`: updates `phase_status.yaml` atomically

### dod_checker.py Integrity Statement
- No changes made to `tools/ops/dod_checker.py` in this design phase.
- No relaxation of strict mode semantics.
- Exit code contract unchanged: 0 = PROVEN, 2 = PARTIAL, 3 = DESIGNED, 4 = ERROR.
- The checker behavioral note above is documentation of observed behavior, not a request to change it.

### Migration Scope
No migration to `repo/core/` in PHASE_3E scope. All source files remain under `core_brain/agents/`.
Decision record: `core/governance/decisions/DECISION_3E_DIRECTORY_PLACEMENT.md` (RECOMMEND KEEP).

---

## 8. Next Step: Gemini Work Order

### Files Gemini Will Create

| File | Content |
|------|---------|
| `core_brain/agents/__init__.py` | Package init (empty or minimal) |
| `core_brain/agents/cost_router.py` | 3-classifier engine: `classify_risk()`, `classify_complexity()`, `has_governance_impact()`, `select_model()` |
| `core_brain/agents/cost_budget.py` | Budget enforcement: `check_budget()`, `record_spend()`, spend ledger I/O |
| `core_brain/agents/model_registry.yaml` | Static tier declarations (T0-T4, models, costs, capabilities) |
| `core_brain/agents/agent_config.yaml` | Per-agent defaults (persona → preferred tier) |
| `core_brain/agents/tests/__init__.py` | Test package init |
| `core_brain/agents/tests/test_cost_router.py` | Determinism, boundary, governance pattern tests |
| `core_brain/agents/tests/test_cost_budget.py` | Budget allow/deny, ledger failure, T0 cap tests |

### Tests Required

**test_cost_router.py** must cover:
- R3 path → T0 (e.g. `core/config.py`)
- R0 path → T3 (e.g. `observability/logs/x.json`)
- L3+ intent → T0 (e.g. `refactor`)
- L0 intent → T3 (e.g. `typo`)
- Governance pattern → T0 override (e.g. `modifies:core/governance/*`)
- Composition: max(risk_floor, complexity_floor) wins
- Replay determinism: `select_model(task)` x100 → identical result

**test_cost_budget.py** must cover:
- Within daily limit → `{allowed: True}`
- Over daily limit → `{allowed: False, reason: "daily_budget_exceeded"}`
- Ledger read failure → `{allowed: False, reason: "ledger_read_failure"}`
- T0 daily call cap → `{allowed: False, reason: "t0_daily_limit"}`
- `record_spend()` appends valid JSONL line

### Evidence Artifacts Required for PROVEN

| Artifact | Path | Must Contain |
|----------|------|-------------|
| Proof JSON | `observability/reports/agents/phase_3e_cost_router_proof.json` | Test results, timestamp, commit_sha |
| Decisions log | `observability/reports/cost_router/decisions.jsonl` | At least 1 valid decision record |
| Spend ledger | `observability/reports/cost_router/spend_ledger.jsonl` | At least 1 valid spend record |
| Activity chain | `observability/logs/activity_feed.jsonl` | 3 events: started, completed, verified (phase_id=PHASE_3E) |

### Activity Emission Requirements (Specification Only)

The verification harness must emit 3 events to `observability/logs/activity_feed.jsonl`:

1. **`started`**: Emitted before any test execution begins.
2. **`completed`**: Emitted after all tests pass AND proof artifact is written. Proof artifact must exist before this event.
3. **`verified`**: Emitted only after `dod_checker --phase PHASE_3E` validates the chain successfully.

Constraints:
- `run_id` must be a single UUID4 hex value, consistent across all 3 events in one verification run.
- All 7 taxonomy keys (see Section 4 table) must be present in every event.
- `emit_mode` must be `runtime_auto` — never `synthetic`.
- Events must have monotonically increasing `ts_epoch_ms`.
- No activity events may be emitted while `commit_sha` is `TODO_SHA`.

### PROVEN Checklist (All Must Be True)

- [ ] `commit_sha` in this DoD replaced with real 40-hex SHA
- [ ] `git cat-file -t <sha>` exits 0 (commit reachable in repo)
- [ ] `activity_feed.jsonl` has started → completed → verified for `PHASE_3E`
- [ ] All 7 taxonomy keys present per event
- [ ] `emit_mode` = `runtime_auto` (not synthetic)
- [ ] `observability/reports/agents/phase_3e_cost_router_proof.json` exists and is readable
- [ ] All tests pass: `pytest core_brain/agents/tests/ -v`
- [ ] `LUKA_REQUIRE_OPERATIONAL_PROOF=1 dod_checker --phase PHASE_3E` exits 0
- [ ] `dod_checker --phase PHASE_3E --update-status-phase` syncs registry to PROVEN
