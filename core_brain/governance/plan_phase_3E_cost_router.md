# Architecture Plan — PHASE_3E: Cost Router + Budget

**Phase ID**: PHASE_3E
**Version**: v1.0
**Author**: CLC
**Date**: 2026-02-12
**Status**: DESIGNED (plan only, no implementation)
**ABI Baseline**: Tier 3 ABI v3.0.0 (frozen)
**Prerequisite Gate**: 6/6 PROVEN (1B, 2, 8, 10, 15.4, OPS)

---

## A. Responsibility Boundaries

### A.1 Cost Router (`core_brain/agents/cost_router.py`)

**Single responsibility**: Classify a task and select the appropriate model tier.

| Does | Does NOT |
|------|----------|
| Reads task dict, extracts path/intent/signals | Execute tasks |
| Runs 3 classifiers in order (Risk, Complexity, Governance) | Call any brain/model API |
| Returns deterministic `{tier, reason, rule, requires_approval}` | Modify pipeline state |
| Emits `MODEL_SELECTED` event to timeline | Override CircuitBreaker decisions |
| Appends decision to `observability/reports/cost_router/decisions.jsonl` | Write to inbox/outbox |

**Purity guarantee**: `select_model(task) -> Dict` is a **pure function** of its input. No side effects beyond logging. Same input always produces same output. No network calls, no file reads beyond registry YAML (loaded once at init).

### A.2 Cost Budget (`core_brain/agents/cost_budget.py`)

**Single responsibility**: Track spend and enforce budget limits.

| Does | Does NOT |
|------|----------|
| Reads spend ledger to calculate running totals | Select models |
| Returns `{allowed, reason, remaining}` for a proposed call | Execute tasks |
| Appends spend records to `spend_ledger.jsonl` | Modify routing decisions retroactively |
| Enforces daily/weekly/per-task/T0-call caps | Override PROVEN verdicts |

**Fail-closed guarantee**: If `check_budget()` cannot read the ledger (I/O error, corruption), it returns `{allowed: False, reason: "ledger_read_failure"}`. Budget enforcement never silently passes.

### A.3 Model Registry (`core_brain/agents/model_registry.yaml`)

**Single responsibility**: Static declaration of available models per tier.

- Read-only at runtime (loaded once, cached in memory)
- No dynamic updates (changes require commit + re-deploy)
- Defines: tier name, model IDs, endpoints, costs, capabilities
- Includes `fallback_chain` for tier escalation

### A.4 Agent Config (`core_brain/agents/agent_config.yaml`)

**Single responsibility**: Per-agent defaults (persona → preferred tier, max concurrency, etc.).

- Read-only at runtime
- Referenced by spawner (Phase 3A, future), not by cost_router directly
- Included in 3E scope for directory coherence only

### A.5 Explicit Non-Powers

The cost router and budget module have **zero execution authority**:

- Cannot call `submit_task()`
- Cannot call `write_result_to_outbox()`
- Cannot modify `phase_status.yaml`
- Cannot write to `interface/inbox/` or `interface/outbox/`
- Cannot instantiate or close `CircuitBreaker` instances
- Cannot call any model API endpoint

These modules are **advisory classifiers**. The coordinator (Phase 3C, future) is the only consumer that acts on their output.

---

## B. Integration Map

### B.1 Modules Consumed (READ only)

| Module | Import | Purpose |
|--------|--------|---------|
| `core.timeline` | `emit_event(trace_id, task_id, event, *, phase, agent_id, detail, extra)` | Log MODEL_SELECTED decisions |
| `core.circuit_breaker` | `CircuitBreaker` (class reference only) | Check breaker state before recommending tier (read, not write) |
| `core.config` | Path constants (`ROOT`, `REPORTS_DIR`) | Resolve report output paths |
| `core_brain/governance/agents.md` | Parsed at design time | Source of L0-L3+ complexity rules |
| `core_brain/governance/pre_claim_contract.md` | Parsed at design time | Source of R0-R3 risk matrix |

### B.2 Modules That Consume Cost Router (future, for awareness)

| Consumer | Calls | Phase |
|----------|-------|-------|
| `core_brain/agents/spawner.py` | `cost_router.select_model(task)` | 3A |
| `core_brain/agents/coordinator.py` | `cost_router.select_model(task)` (via spawner) | 3C |

### B.3 Timeline Emit Points

Cost router emits exactly **1 event type** per routing decision:

```
emit_event(
    trace_id=trace_id,
    task_id=task_id,
    event="MODEL_SELECTED",
    phase="cost_router",
    agent_id="cost_router",
    detail=json.dumps({
        "tier": "T2",
        "risk": "R1",
        "complexity": "L1",
        "governance_impact": false,
        "reason": "risk=R1,complexity=L1"
    }),
)
```

**Note**: The actual ABI parameter is `event=` (not `event_type=`). Blueprint V3 Section 3.3.3 uses `event_type` — implementer must use `event=` to match `core/timeline.py` signature.

Cost budget emits exactly **1 event type** per budget breach:

```
emit_event(
    trace_id=trace_id,
    task_id=task_id,
    event="BUDGET_BREACH",
    phase="cost_budget",
    agent_id="cost_budget",
    detail=json.dumps({
        "limit_type": "daily_usd",
        "spent": 4.82,
        "limit": 5.00,
        "action": "downgrade_tier"
    }),
)
```

All `emit_event()` calls MUST be wrapped in `try/except` (non-fatal). Timeline emission failure must never block routing decisions.

### B.4 Activity Chain Recording

Activity events for PHASE_3E verification are written to `observability/logs/activity_feed.jsonl` (the standard path per `dod_checker.py` line 168).

Required taxonomy per event (matches `REQUIRED_TAXONOMY_KEYS`):

```json
{
    "action": "started|completed|verified",
    "phase_id": "PHASE_3E",
    "emit_mode": "runtime_auto",
    "verifier_mode": "operational_proof",
    "tool": "cost_router",
    "run_id": "<uuid4_hex>",
    "ts_epoch_ms": 1770879143017,
    "ts_utc": "2026-02-12T10:00:00Z"
}
```

Activity events are emitted by the **test/verification harness**, not by cost_router.py itself. The router is a pure classifier — activity chain proves the verification loop ran, not that routing happened.

### B.5 Evidence Artifacts

| Artifact | Path | Created By |
|----------|------|-----------|
| Routing decisions log | `observability/reports/cost_router/decisions.jsonl` | `cost_router.py` (append per call) |
| Spend ledger | `observability/reports/cost_router/spend_ledger.jsonl` | `cost_budget.py` (append per spend) |
| Verification proof | `observability/reports/phase3E/cost_router_proof.json` | Test harness / `dod_checker.py` |

---

## C. Governance Guarantees

### C.1 No Silent Model Escalation

**Rule**: Every tier selection is logged to `decisions.jsonl` with full reasoning. There is no code path that changes the selected tier without appending a decision record.

**Enforcement**:
- `select_model()` returns the decision dict
- The caller (spawner/coordinator) logs it before acting
- If a Sentry escalation occurs (output flagged → retry at higher tier), that produces a **new** decision record with `reason: "sentry_escalation:T2->T1"`

**Verification**: Replay test — run `select_model(task)` N times with same input, assert all N results are identical.

### C.2 Budget Breach = Fail-Closed

**Rule**: If `check_budget()` returns `{allowed: False}`, the caller MUST NOT proceed with the model call.

**Enforcement**:
- `check_budget()` is called before every brain invocation (by spawner, Phase 3A)
- On `allowed: False`:
  - If `reason` is `daily_budget_exceeded` or `weekly_budget_exceeded` → attempt tier downgrade
  - If no lower tier available → reject task with `budget_exhausted`
  - If `reason` is `ledger_read_failure` → hard fail (no silent pass)

**Critical**: Budget module never returns `{allowed: True}` on I/O error. Default is deny.

### C.3 All Routing Decisions Logged

**Rule**: Zero routing decisions happen off-ledger.

**Decision record schema** (`decisions.jsonl` line format):
```json
{
    "ts": "ISO8601",
    "task_id": "task_YYYYMMDD_HHMMSS_XXXXXX",
    "tier_selected": "T0|T1|T2|T3|T4",
    "risk_level": "R0|R1|R2|R3",
    "complexity_level": "L0|L1|L2|L3_plus",
    "governance_impact": true|false,
    "governance_reason": "string|null",
    "reason": "risk=R1,complexity=L1",
    "requires_approval": true|false,
    "classifier_chain": "1=R1,2=L1,3=none"
}
```

### C.4 Evidence Artifact Required Per Decision

Every `decisions.jsonl` entry IS the evidence. The file itself is the audit trail. `dod_checker.py` validates:
1. File exists at `observability/reports/cost_router/decisions.jsonl`
2. Each line is valid JSON
3. Required keys present (`tier_selected`, `risk_level`, `complexity_level`, `governance_impact`)

---

## D. Failure Modes

### D.1 Misclassification

| Scenario | Consequence | Mitigation |
|----------|-------------|-----------|
| R1 file classified as R0 | Lower-tier model handles sensitive-ish work | Path prefix matching is deterministic — misclassification means rule set is wrong, not runtime error. Fix: update RISK_RULES |
| L3+ task classified as L1 | Underpowered model attempts complex work | Sentry output guard catches poor quality → triggers tier escalation → logged as new decision |
| Governance task missed | Non-sovereign model makes policy change | Pattern match on `modifies:core/governance/*` is prefix-based. Miss requires the pattern list to be incomplete. Fix: add pattern |

**Key insight**: Misclassification is a **rule authoring** error, not a **runtime** error. The classifier is deterministic — it always faithfully executes its rules. The risk is rules being incomplete.

**Mitigation**: `test_cost_router.py` must include boundary cases for every risk level and complexity level.

### D.2 Budget Overflow

| Scenario | Consequence | Mitigation |
|----------|-------------|-----------|
| Spend ledger corrupted | Budget check cannot determine spend | `check_budget()` returns `{allowed: False, reason: "ledger_read_failure"}` (fail-closed) |
| Concurrent writes to ledger | Race condition → double-counting or under-counting | Append-only JSONL + advisory file lock. Over-count is safe (conservative). Under-count is bounded by per-task cap |
| Daily spend exactly at limit | Edge case: $5.00 spent, next call costs $0.001 | Strict `>=` comparison: `if daily_spent + cost > limit` (not `>=`). At-limit calls that fit within budget are allowed |

### D.3 Missing Registry Entry

| Scenario | Consequence | Mitigation |
|----------|-------------|-----------|
| `model_registry.yaml` missing | No models available | `__init__` raises `FileNotFoundError`. Module cannot start. Fail-closed |
| Tier selected but no models in that tier | Empty model list | `_pick_model(tier)` raises `ValueError(f"no_models_in_tier:{tier}")`. Caller must handle (downgrade or reject) |
| Model endpoint unreachable | API call will fail | Not cost_router's concern — CircuitBreaker handles this at the spawner/brain layer |

### D.4 Event Emission Failure

| Scenario | Consequence | Mitigation |
|----------|-------------|-----------|
| `emit_event()` raises (disk full, permissions) | Decision still made, just not logged to timeline | try/except wrapper. Decision IS still logged to `decisions.jsonl` (separate I/O path) |
| `decisions.jsonl` write fails | Decision made but no audit trail | Raise exception. Routing must NOT proceed without audit trail. This is the one non-negotiable I/O path |
| `spend_ledger.jsonl` write fails | Spend not recorded → budget may allow over-spend | Raise exception. Budget record failure = hard stop. Next `check_budget()` would under-count |

**Summary**: Timeline emit = soft (non-fatal). Decisions log = hard (fatal). Spend ledger = hard (fatal).

---

## E. Activity Taxonomy Definition for PHASE_3E

### E.1 Event Semantics

| Action | When Emitted | By Whom | Meaning |
|--------|-------------|---------|---------|
| `started` | Test harness begins PHASE_3E verification | Test suite / verification script | "Verification of cost router + budget module has begun" |
| `completed` | All test assertions pass, evidence artifacts written | Test suite / verification script | "Cost router produces correct classifications, budget enforces limits, audit trail is complete" |
| `verified` | `dod_checker --phase PHASE_3E` exits 0 | `dod_checker.py` or manual verification | "Machine-verified: activity chain valid, evidence exists, commit reachable, taxonomy ok" |

### E.2 Required Fields Per Event

```json
{
    "action": "started",
    "phase_id": "PHASE_3E",
    "emit_mode": "runtime_auto",
    "verifier_mode": "operational_proof",
    "tool": "cost_router",
    "run_id": "<consistent_uuid4_hex_across_all_3_events>",
    "ts_epoch_ms": "<epoch_ms>",
    "ts_utc": "<ISO8601>"
}
```

**run_id consistency**: All 3 events (started, completed, verified) in a single verification run MUST share the same `run_id`. This is how `dod_checker` correlates the chain.

### E.3 What Proves "Operational" (not synthetic)

Per `dod_checker.py` strict mode logic:
1. `emit_mode` must be `"runtime_auto"` (not `"synthetic"`)
2. `verifier_mode` must be `"operational_proof"`
3. Activity events must exist in `observability/logs/activity_feed.jsonl`
4. All `REQUIRED_TAXONOMY_KEYS` must be present: `phase_id`, `emit_mode`, `verifier_mode`, `tool`, `run_id`, `ts_epoch_ms`, `ts_utc`

---

## F. File Inventory

| File | Action | Owner | Purpose |
|------|--------|-------|---------|
| `core_brain/agents/cost_router.py` | CREATE | Gemini (impl) | 3-classifier routing engine |
| `core_brain/agents/cost_budget.py` | CREATE | Gemini (impl) | Spend tracking + budget enforcement |
| `core_brain/agents/model_registry.yaml` | CREATE | CLC (config) | Static model tier declarations |
| `core_brain/agents/agent_config.yaml` | CREATE | CLC (config) | Per-agent defaults (used by 3A) |
| `core_brain/agents/__init__.py` | CREATE | Gemini | Package init (empty or minimal) |
| `core_brain/agents/tests/__init__.py` | CREATE | Gemini | Test package init |
| `core_brain/agents/tests/test_cost_router.py` | CREATE | CLC (arch) + Gemini (impl) | Determinism + boundary tests |
| `core_brain/agents/tests/test_cost_budget.py` | CREATE | Gemini | Budget enforcement tests |
| `observability/reports/cost_router/` | CREATE dir | CLC | Report output directory |
| `observability/reports/cost_router/.gitkeep` | CREATE | CLC | Keep empty dir in git |
| `observability/reports/phase3E/` | CREATE dir | CLC | Phase evidence directory |
| `docs/dod/DOD__PHASE_3E.md` | CREATE | CLC | Definition of Done |

---

## G. Risk Assessment

### G.1 Enterprise Scaling Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| `decisions.jsonl` grows unbounded | HIGH (1 line per routing call) | Disk pressure over months | `core/retention.py` already handles JSONL rotation. Add `cost_router/decisions.jsonl` to retention config |
| `spend_ledger.jsonl` grows unbounded | HIGH | Same | Same retention policy |
| Concurrent coordinator instances write same ledger | MEDIUM (future multi-agent) | Race condition in spend accounting | Advisory file lock (flock) on ledger write. Append-only semantics make partial writes safe |
| Model pricing changes | CERTAIN (vendors update prices) | Budget calculations become inaccurate | Pricing is in `model_registry.yaml` — update YAML, no code change. But requires re-verification |

### G.2 Cross-Repo Compatibility Concerns

| Concern | Current State | Future Risk | Prevention |
|---------|--------------|-------------|-----------|
| `model_registry.yaml` is repo-local | OK — single repo | Multi-repo would need shared registry | Registry MUST use relative paths only. No `/home/` paths. No repo-specific assumptions |
| `decisions.jsonl` path is hardcoded relative | OK — `observability/reports/cost_router/` | Cross-repo aggregator would need to know this path | Document path in ABI contract. Future aggregator reads via `core/config.py` constant |
| Budget is per-repo | OK — single budget | Multi-repo spend must aggregate | Budget module reads from local ledger only. Cross-repo aggregation is a FUTURE module (not 3E scope) |

**Rule**: Phase 3E introduces ZERO cross-repo coupling. All paths are relative to `core.config.ROOT`. All imports are intra-repo.

### G.3 ABI Drift Prevention

| Surface | Drift Risk | Prevention |
|---------|-----------|-----------|
| `emit_event()` signature | LOW (parameter name `event` already frozen) | Test imports `emit_event` and asserts parameter names via `inspect.signature()` |
| `CircuitBreaker` interface | LOW (constructor frozen since ops hardening) | Test imports and asserts `failure_threshold` + `recovery_timeout_sec` params exist |
| `sign_envelope()` | MEDIUM (blueprint says `seal_envelope`) | **Errata**: Blueprint must be corrected to `sign_envelope`. Test asserts import succeeds |
| Activity feed taxonomy | LOW (7 keys frozen since Phase 15.5.4) | Test emits event and verifies all 7 `REQUIRED_TAXONOMY_KEYS` present |

### G.4 Future Aggregator Compatibility

The cost router is designed so a future aggregator (cross-agent dashboard, spend summary) can:

1. **Read `decisions.jsonl`** — append-only, one JSON object per line, schema documented in C.3
2. **Read `spend_ledger.jsonl`** — append-only, one JSON object per line, schema in V3 Section 3.9
3. **Replay any decision** — `select_model(task_dict)` is deterministic. Feed same input → same output
4. **Verify via `dod_checker`** — `--phase PHASE_3E` checks the same 7 sections as all other phases

No special aggregator hooks are needed. JSONL is the universal interchange format.

---

## H. Summary Table

| Dimension | Status | Notes |
|-----------|--------|-------|
| Architecture completeness | DESIGNED | All boundaries, interfaces, failure modes defined |
| ABI compatibility | ALIGNED (2 errata noted) | `event` not `event_type`, `sign_envelope` not `seal_envelope` |
| Governance safety | PRESERVED | No execution power, fail-closed budget, full audit trail |
| Implementation risk | LOW | Pure logic module, no network I/O, no state mutation beyond JSONL append |
| Cross-repo coupling | ZERO | All paths relative, all imports intra-repo |
| Strict mode impact | NONE | Does not modify `dod_checker.py` logic |
| CircuitBreaker interaction | READ-ONLY | Checks state, never opens/closes breakers |
| Prerequisite gate | OPEN (6/6 PROVEN) | Ready for implementation |
