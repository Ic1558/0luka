# save-now v2 (artifact-only) — Contract (KEEP layout)

## Metadata
- scope: save-now v2 artifact-only persistence
- created: 2026-01-29
- updated: 2026-01-29
- status: ACTIVE (layout keep)
- owner: core_brain/governance
- version: 2.0 (KEEP)

## Purpose
Define the **authoritative** layout and schema for save-now v2 outputs while preserving the current flat layout under `observability/artifacts/tasks/<trace_id>/`.

## Goal
Guarantee that save-now v2 writes artifacts only (no git, no run_tool), produces deterministic paths, and provides a stable reader contract for consumers.

---

## 1) Authoritative layout (KEEP)

Root:

```
$ROOT/observability/
  artifacts/
    tasks/
      <trace_id>/
        plan.md
        result.json
        reply.md
        meta.json
        timeline.jsonl
    handoff_latest.json
  logs/
    save_now_failures.log
```

### Trace ID rules
- `<trace_id>` is the folder name (no extra nesting).
- Must be unique per handoff run.
- Must **not** include `/` or `..`.

---

## 2) File semantics

### plan.md
- Type: Markdown (UTF-8)
- Meaning: Plan/intent before execution

### result.json
- Type: JSON object
- Meaning: Structured result of execution

### reply.md
- Type: Markdown (UTF-8)
- Meaning: Final user-facing response

### meta.json (authoritative)
- Type: JSON object
- Meaning: Primary metadata for this trace
- Must exist for any phase written

### timeline.jsonl (append-only)
- Type: JSON Lines (1 event per line)
- Meaning: Audit timeline for this trace

### handoff_latest.json (atomic pointer)
- Type: JSON object
- Meaning: Single latest pointer for consumers; **must** be written atomically

---

## Non-goals
- This contract does **not** define `sessions/*`, `meta_merged.json`, or `inflight/*` layouts.
- Any new layout proposals must be explicit version bumps, not implicit extensions.

---

## 3) Schemas (current, strict-minimum)

### 3.1 meta.json (v1)
**Required (currently emitted):**
- `trace_id` (string)
- `agent_id` (string)
- `created_at` (ISO-8601 UTC Z)
- `updated_at` (ISO-8601 UTC Z)
- `phases` (object) — keys: `plan|done|reply` with `{path, ts}`
- `status` (string) — `IN_PROGRESS|DONE|REPLIED` (at least these)
- `title` (string)

**Optional (currently emitted when present):**
- `task_id` (string)
- `tags` (array of string)

**Reserved (not yet emitted; future-safe):**
- `schema_version`
- `inputs`
- `outputs`
- `root`

**Example (minimal):**
```json
{
  "trace_id": "trace-xyz",
  "agent_id": "codex",
  "created_at": "2026-01-29T00:00:00Z",
  "updated_at": "2026-01-29T00:00:01Z",
  "title": "trace_id=trace-xyz phase=plan",
  "phases": {"plan": {"path": "plan.md", "ts": "2026-01-29T00:00:01Z"}},
  "status": "IN_PROGRESS"
}
```

### 3.2 timeline.jsonl (v1)
**Required fields (currently emitted):**
- `ts` (ISO-8601 UTC Z)
- `trace_id` (string)
- `task_id` (string, may be empty)
- `agent_id` (string)
- `phase` (string)
- `path` (string)
- `title` (string)

**Example line:**
```json
{"ts":"2026-01-29T00:00:01Z","trace_id":"trace-xyz","task_id":"","agent_id":"codex","phase":"plan","path":"plan.md","title":"trace_id=trace-xyz phase=plan"}
```

### 3.3 handoff_latest.json (v1)
**Required (currently emitted):**
- `ts` (ISO-8601 UTC Z)
- `trace_id` (string)
- `title` (string)
- `agent_id` (string)
- `updated_at` (ISO-8601 UTC Z)
- `dir` (string) — absolute path to `tasks/<trace_id>`
- `paths` (object) — includes `meta`, `plan`, `done`, `reply`

**Example (minimal):**
```json
{
  "ts": "2026-01-29T00:00:01Z",
  "trace_id": "trace-xyz",
  "title": "trace_id=trace-xyz phase=plan",
  "agent_id": "codex",
  "updated_at": "2026-01-29T00:00:01Z",
  "dir": "/Users/icmini/0luka/observability/artifacts/tasks/trace-xyz",
  "paths": {
    "meta": "/Users/icmini/0luka/observability/artifacts/tasks/trace-xyz/meta.json",
    "plan": "/Users/icmini/0luka/observability/artifacts/tasks/trace-xyz/plan.md",
    "done": "/Users/icmini/0luka/observability/artifacts/tasks/trace-xyz/done.json",
    "reply": "/Users/icmini/0luka/observability/artifacts/tasks/trace-xyz/reply.md"
  }
}
```

---

## 4) Guarantees
1. **Artifact-only**
   - No `git add`, `git commit`, `push`, or `promote`.
   - No fallback to `run_tool.zsh`.

2. **Atomic writes**
   - `handoff_latest.json` is written via temp + rename.
   - `meta.json` is written via temp + rename.

3. **Deterministic IO**
   - Wrapper fails hard if phase input file is missing.
   - Output path is deterministic: `observability/artifacts/tasks/<trace_id>/...`

4. **No catalog dependency**
   - v2 must not require `tools/CATALOG.md`.
   - Any new `catalog not found` errors are regressions.

---

## 5) Reader/Consumer rules
- Do **not** scan `tasks/` to find latest.
- Always read **only** `observability/artifacts/handoff_latest.json`.
- If the pointer path is missing → fail closed (report error, do not guess).
- `observability/reports/handoff_latest.*` is legacy/human-facing and **not** an entrypoint.

---

## 6) Verification checklist
1. Run wrapper for phase `plan`.
2. Confirm `observability/artifacts/tasks/<trace_id>/` exists.
3. Confirm `handoff_latest.json` updated.
4. Confirm no new `catalog not found` entry in `save_now_failures.log`.

### 6.1 Automated proof (doc-only)
Run this once to capture evidence without touching git:

```zsh
ROOT="$HOME/0luka"
trace_id="trace-v2-proof-$(date -u +%H%M%S)"
tmp_plan="/tmp/save_now_test_plan.md"
echo "# Plan\n\nGoal: save-now v2 proof" > "$tmp_plan"

ROOT="$ROOT" zsh "$ROOT/observability/tools/memory/save_now_wrapper.zsh" \
  --agent-id codex \
  --trace-id "$trace_id" \
  --phase plan \
  --files "$tmp_plan"

test -d "$ROOT/observability/artifacts/tasks/$trace_id"
```

---

## 7) Evidence note
As of this contract, repository logs show **no new** `catalog not found: tools/CATALOG.md` entries beyond legacy timestamps. A fresh wrapper proof run should be captured for full closure.
