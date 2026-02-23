# Health Cache Contract Unification v1

**Status:** DESIGN — awaiting approval before implementation
**Ticket:** B3.2
**Author:** GMX / Antigravity
**Date:** 2026-02-23
**Effective after:** approval + Step 4 seal

---

## 1. Problem Statement

Two files exist with near-identical names and overlapping semantic intent:

| File | Writer | Schema | Purpose |
|---|---|---|---|
| `observability/artifacts/health_latest.json` | `core/health.py` | `health_v1` | Full system health (tests, dispatcher, queues) |
| `observability/telemetry/health.latest.json` | `tools/bridge_dispatch_watchdog.py` | (unnamed) | Bridge watchdog ping only |

`mission_control.py` reads **only** the first file (`health_latest.json`). The second file is written but
never consumed by any current reader — yet its name implies it is *the* health truth, causing confusion
in dashboards, snapshots, and ATG context.

---

## 2. SOT Declaration

```
SOT = observability/artifacts/health_latest.json
```

This path is **immutable after this contract is sealed**. No other file may use the word `health` and
the word `latest` together in `observability/` unless it carries `schema_version: health_v1` and was
written by the declared writer below.

---

## 3. Canonical Schema (health_v1.1 — forward extension, non-breaking)

Fields added in v1.1 are marked `[NEW]`. Existing fields are unchanged.

```json
{
  "schema_version": "health_v1",
  "ts_utc": "2026-02-23T04:00:00Z",      // [NEW] canonical key; ts kept as alias
  "ts": "2026-02-23T04:00:00Z",           // legacy alias, kept for ≥2 cycles
  "producer": "core/health.py",            // [NEW] provenance assertion
  "head_sha": "88fabf1...",               // [NEW] git HEAD at write time; null if unavailable
  "status": "healthy | degraded",
  "tests_failed": 0,                      // [NEW] top-level mirror of tests.failed
  "failed_suites": [],                    // [NEW] list of suite names that failed
  "issues": [],
  "dispatcher": { "...": "..." },
  "last_dispatch": { "...": "..." },
  "queues": { "...": "..." },
  "schemas": { "...": "..." },
  "tests": { "...": "..." }
}
```

All existing fields remain structurally identical. This is a **non-breaking additive extension**.

---

## 4. Staleness / Error Policy — STRICT (no proof-pack fallback)

When `mission_control.py` reads the SOT cache, it MUST apply these states in order:

| State | Trigger | `dev_health` result | `dev_health_source` |
|---|---|---|---|
| `cache_missing` | File does not exist | `UNKNOWN` | `"none"` |
| `cache_unparseable` | JSON error or not a dict | `UNKNOWN` | `"none"` |
| `cache_stale` | `ts` / `ts_utc` absent OR `age > 600s` | `UNKNOWN` | `"cache_stale"` |
| `cache_mismatch` | `head_sha` present AND `head_sha != git HEAD` AND `age > 60s` | `UNKNOWN` | `"cache_mismatch"` |
| `cache_fresh` | All above pass | from `tests.failed` or `status` | `"cache"` |

### ⚠ No proof-pack fallback

**When cache yields `UNKNOWN` for any reason, `dev_health` stays `UNKNOWN`.  
`mission_control` MUST NOT fall back to proof-pack inference.**

Rationale: proof-packs are older than the cache by design. Falling back to a proof-pack when the cache
is stale produces a false-positive "HEALTHY" signal from even older evidence — a double-stale condition
that is worse than explicit UNKNOWN.

Action on UNKNOWN:

- Display `dev_health: UNKNOWN` in dashboard
- Log the specific staleness code in `issues[]`
- Do NOT suppress or substitute

### Backward-compat: missing `head_sha` (Cycles 1–2)

For 1–2 cycles after implementing Step 2, the cache may have been written by the old `health.py`
without `head_sha`. The mismatch check MUST be skipped when `head_sha` is `null` or absent:

```python
cached_sha = payload.get("head_sha")
if cached_sha is not None and age_sec > 60:
    # perform SHA mismatch check
```

If `head_sha` is absent → skip check, treat as `cache_fresh` (age and parse checks still apply).

### Backward-compat: `ts` vs `ts_utc`

The reader must accept **either** key for timestamp parsing (already the case in `mission_control.py`
line 257: `payload.get("ts") or payload.get("ts_utc")`). No change required.

---

## 5. Impact Matrix

### Writers

| Component | File | Action |
|---|---|---|
| `core/health.py` | `observability/artifacts/health_latest.json` | **Sole authorized writer.** Add `head_sha`, `ts_utc`, `producer`, `tests_failed`, `failed_suites` to return dict. |
| `tools/bridge_dispatch_watchdog.py` | `observability/telemetry/health.latest.json` | **Rename output.** Change to `observability/telemetry/bridge_watchdog.latest.json`. One-line diff. |

### Readers

| Component | Path consumed | Action |
|---|---|---|
| `tools/mission_control.py` | `observability/artifacts/health_latest.json` | Add `cache_mismatch` check; enforce no proof-pack fallback on UNKNOWN. |
| `system/tools/tk/tk_evidence_pack.py` | `observability/telemetry/tk_health.latest.json` | **No change.** Uses `tk_health` namespace, unaffected. |
| ATG snapshots / dashboard | reads MC output | No change — staleness surfaces via `dev_health: UNKNOWN`. |

### Orphan after rename

`observability/telemetry/health.latest.json` — after Step 1, this file will stop being updated.
It becomes a frozen artifact with the timestamp of the last watchdog run.
**Do NOT delete it before Step 4 seal** (preserves forensic evidence).
Delete or archive after seal is accepted.

---

## 6. Migration Steps + Proof-Pack Plan

### Step 1 — Rename watchdog output (≤5 min, 1-line diff)

**File:** `tools/bridge_dispatch_watchdog.py` line 67

```python
# BEFORE
telemetry_path = root / "observability" / "telemetry" / "health.latest.json"
# AFTER
telemetry_path = root / "observability" / "telemetry" / "bridge_watchdog.latest.json"
```

**Proof for step:**

- `git diff tools/bridge_dispatch_watchdog.py` → exactly 1 line changed
- Run watchdog: `python3 tools/bridge_dispatch_watchdog.py`
- Assert `observability/telemetry/bridge_watchdog.latest.json` exists
- Assert `observability/telemetry/health.latest.json` timestamp has NOT advanced

---

### Step 2 — Extend `health.py` writer (additive, non-breaking)

**File:** `core/health.py` — `check_health()` return dict

Add to the return dict in `check_health()`:

- `ts_utc`: same value as `ts` (alias)
- `producer`: `"core/health.py"` (constant string)
- `head_sha`: result of `git rev-parse HEAD` subprocess; `null` on failure (never crash)
- `tests_failed`: `tests_result["failed"] if tests_result else None`
- `failed_suites`: list of `k` where `details[k].startswith("fail:")`, or `[]`

**Proof for step:**

- `python3 core/health.py --full --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'head_sha' in d and 'ts_utc' in d and 'producer' in d, d.keys()"`
- Confirm `head_sha` matches `git rev-parse HEAD`
- Confirm `failed_suites` is a list (may be empty)
- Run `python3 core/verify/test_health.py` → must pass (schema_version field unchanged)

---

### Step 3 — Update `mission_control.py` reader

**File:** `tools/mission_control.py` — `_read_health_cache()`

Changes:

1. After existing `age_sec > max_age_sec` check, add `cache_mismatch` check (with `head_sha` guard for backward-compat — see §4).
2. When any check returns `UNKNOWN`, **do NOT fall through to proof-pack inference** — return immediately.
3. Update `dev_health_source` strings to include `"cache_mismatch"`.

**Proof for step:**

- Run `python3 tools/mission_control.py --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['dev_health_source'])"`
  - Expected: `"cache"` when cache is fresh and SHA matches
- Manually set `head_sha` in `health_latest.json` to `"deadbeef"`, run MC:
  - Expected: `dev_health_source: "cache_mismatch"`, `dev_health: "UNKNOWN"`
- Run `python3 core/verify/test_health.py` and `python3 core/verify/test_cli.py` → must pass

---

### Step 4 — SOT Pack Seal

After Steps 1–3 all pass:

1. Run `python3 core/health.py --full` (triggers cache write with new fields)
2. Run `python3 tools/mission_control.py` (confirms `dev_health_source: cache`)
3. Run `python3 core/health.py --full` again to confirm 20/20 tests pass
4. Commit with message: `contract(health): unify cache SOT (B3.2) — bridge_watchdog renamed, head_sha added`
5. Create proof pack:
   - `observability/artifacts/health_latest.json` (with `head_sha`, `ts_utc`, `producer`)
   - `observability/telemetry/bridge_watchdog.latest.json` (new watchdog output)
   - `git diff` of Steps 1–3 combined
   - `python3 core/health.py --full` terminal output (20/20 pass)
6. Push → verify CI green on `governance-check`, `phase1a-scope-lock`, `phase1a-smoke`
7. Archive (do not delete) `observability/telemetry/health.latest.json` in place

---

## 7. What This Contract Does NOT Change

- `observability/telemetry/ram_monitor.latest.json` — separate subsystem (see B3.3)
- `observability/telemetry/ram_monitor.state.json` — separate subsystem (see B3.3)
- `observability/telemetry/tk_health.latest.json` — TK subsystem, unaffected
- `observability/artifacts/dispatch_latest.json` — dispatcher subsystem, unaffected
- Any existing proof-pack format or seal process

---

## 8. Decision Required Before Implementation

- [ ] Approve SOT path lock (`observability/artifacts/health_latest.json`)
- [ ] Approve strict UNKNOWN policy (no proof-pack fallback)
- [ ] Approve rename: `health.latest.json` → `bridge_watchdog.latest.json`
- [ ] Approve schema extension (additive, non-breaking)
- [ ] Approve migration order: Step 1 → 2 → 3 → 4 (seal)

*Sign-off required before any code is changed.*
