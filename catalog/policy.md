# Catalog Policy (Touchless Overlay)

## Metadata
- version: 1.1
- owner: codex
- creator: codex
- edited_by: [codex]
- status: active
- scope: catalog routing + dry-run gate
- created: 2026-01-27
- updated: 2026-01-27
- current_blocks:
  - dry-run gate (max 5 attempts)
  - tmp-first output staging
  - scoring rubric (threshold ≥ 95)
  - ledger logging
  - retention
  - alerting
  - escalation levels
  - override procedure
  - auditing format
  - registry schema
  - scoring examples

## Change Log
- 2026-01-27: v1.0 created (dry-run gate, tmp-first, scoring rubric, requirements).
- 2026-01-27: v1.1 added ledger/retention/alerting, escalation, override, audit format, registry schema, examples.

## Signatures
- codex: unsigned

## Purpose
Define a deterministic catalog gate that **dry-runs every attempt** until a tool match scores **≥ 95/100**, with a hard cap of **5 attempts**, and **tmp-first** output staging.

## Goal
Guarantee that no catalog execution occurs without a high-confidence match (≥95), while preserving auditability via tmp-first dry-run reports.

## Requirements
1) Deterministic scoring with a fixed rubric (no ad-hoc weights).
2) Maximum 5 dry-run attempts per request.
3) No execution if score < 95.
4) Dry-run artifacts must be written to `/tmp` first.
5) Promotion to final output only on score ≥ 95.
6) Failure must be explicit, with ranked alternatives and reasons.
7) All attempts must be traceable (request_id required).

## Inputs
- request_id (required)
- requested_tool (string)
- requested_action (string, optional)
- tags (list, optional)
- required_capabilities (list, optional)
- risk_class (low/medium/high)
- registry_source (catalog registry path)

## Outputs
- Dry-run report (JSON) in `/tmp`
- Final execution output only if score ≥ 95
- Failure report if attempts exhausted

## Policy: Dry-Run Gate
1) Default behavior is **dry-run**.
2) Score the candidate tool per the rubric below.
3) If `score >= 95`, execution may proceed.
4) If `score < 95`, return a dry-run report + top suggestions.
5) Retry dry-run scoring up to **5 attempts**.
6) If still `< 95` after 5 attempts, **fail** with reasons and suggestions.

## Policy: TMP-First Output
- All dry-run outputs must be written to `/tmp` first.
- Only when `score >= 95` is output promoted to the final destination.

Example staging path:
```
/tmp/catalog_dryrun/<request_id>/attempt_1.json
```

## Policy: Traceability
- Each attempt must include `request_id` and `attempt`.
- The same `request_id` must be used for all 1–5 attempts.

## Policy: Determinism
- Given identical inputs and registry state, scoring must be identical.
- If registry state changes, attempts reset (new request_id).

## Policy: Ledger Logging
- Log an event for each attempt: `catalog.dryrun.attempt`.
- Log a success event: `catalog.execute.allowed` when score ≥ 95.
- Log a failure event: `catalog.execute.denied` after 5 attempts without passing.
- Each ledger record must include: `request_id`, `attempt`, `score`, `selected_tool` (if any), and `ts`.

## Policy: Retention
- Keep dry-run reports in `/tmp/catalog_dryrun/` for 24 hours.
- Keep final reports in their destination per normal retention policy.
- Do not delete ledger entries.

## Policy: Alerting
- Alert only on `catalog.execute.denied` (after 5 failed attempts).
- Alert payload must include: `request_id`, `score`, `top_candidates`, and `reason`.
- Suppress repeat alerts for the same `request_id`.

## Policy: Escalation Levels
- Level 0 (info): dry-run attempt logged, no alert.
- Level 1 (warn): repeated low score (attempts 3–4), no alert unless configured.
- Level 2 (error): `catalog.execute.denied` after 5 attempts (alert required).

## Policy: Override Procedure
- Overrides are **disabled by default**.
- If an override is allowed, it must be explicit:
  - `override=true`
  - `override_reason` (required, non-empty)
  - `override_actor` (required)
- Overrides must be logged to the ledger as `catalog.override.used`.
- Overrides must still write dry-run output to `/tmp` before execution.

## Auditing Format
All audit records (dry-run or execution) must be JSON with the following minimum fields:
- `ts`
- `event`
- `request_id`
- `attempt`
- `score`
- `selected_tool` (nullable)
- `dryrun` (bool)
- `reason` (nullable)
- `override` (bool)
- `override_actor` (nullable)
- `override_reason` (nullable)

Event names:
- `catalog.dryrun.attempt`
- `catalog.execute.allowed`
- `catalog.execute.denied`
- `catalog.override.used`

## Registry Schema (Minimal)
Each tool entry must include:
- `name` (string)
- `aliases` (list of strings)
- `capabilities` (list of strings)
- `tags` (list of strings)
- `risk_class` (`low|medium|high`)
- `deprecated` (bool)
- `description` (string)

Optional:
- `examples` (list)
- `owner` (string)
- `last_success_ts` (string)

## Scoring Examples

Example A (passes):
- exact name match: +40
- full capability: +20
- tags (2): +10
- scope ok: +10
- recent success: +10
- risk low: +5
- deprecated: 0
Total = 95 → execute

Example B (fails):
- alias match: +25
- partial capability: +10
- tags (1): +5
- scope ok: +10
- recent success: +5
- risk medium: 0
Total = 55 → dry-run only

## Scoring Rubric (0–100)

### 1) Exact Name Match (0–40)
- +40 exact tool name
- +25 alias match
- +10 fuzzy match (same stem)

### 2) Capability Match (0–20)
- +20 full capability match
- +10 partial match
- 0 mismatch

### 3) Tag/Keyword Match (0–15)
- +5 per tag match (max +15)

### 4) Scope & Policy Safety (0–10)
- +10 in-scope
- 0 unknown
- −20 policy violation

### 5) Recency / Proven Success (0–10)
- +10 successful use within last N runs
- +5 seen before
- 0 unknown

### 6) Risk Class (−15 to +5)
- +5 low risk
- 0 medium
- −15 high risk

### 7) Deprecation / Warnings (−30)
- −30 deprecated or superseded
- 0 normal

## Decision Threshold
- **Execute only if score ≥ 95.**
- Otherwise: **dry-run only** with ranked alternatives.

## Conflict Resolution
If multiple candidates score ≥ 95:
1) prefer exact name match
2) then highest capability match
3) then highest score
4) if tie remains, fail and request disambiguation

## Output Contract (per attempt)
- attempt (1–5)
- score
- dryrun = true
- top_candidates (ranked list)
- reason (why below threshold)

On success:
- dryrun = false
- score >= 95
- selected_tool
- promoted_output_path

## Failure Condition
If score remains `< 95` after 5 attempts:
- fail hard
- include ranked candidates and reasons

## Non-Goals
- No auto-execution without passing the threshold.
- No silent fallback to unregistered tools.
