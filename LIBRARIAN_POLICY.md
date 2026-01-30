# Librarian Policy (SOT Enforcement for 0luka)

## Scope
- **Responsibility**: Move scatter files to canonical locations, maintain state files, update luka.md on transitions.
- **Forbidden**: Do NOT touch `core/`, `core_brain/`, or modify production code. State files only.

## Threshold Triggers (luka.md update)
Update luka.md only on:
- Phase change
- System health threshold change
- Canonical paths / quick commands change
- Incident / recovery
- Human ask
- Do NOT update on every save-now

## Scatter → Canonical Rules
Move these patterns to canonical (if not already there):
- `reports/summary/*.md` → `reports/summary/latest.md`
- `notes/lessons/ref/**` → `memory/**`
- `outputs/evidence/run logs per task/**` → `artifacts/**`
- `snapshots/status json/yaml` → `state/**`
- `runtime logs` → `logs/<component>/`

Every move MUST:
- Include UTC timestamp (`ts_utc`)
- Record to `state/recent_changes.jsonl` (append-only)

If source and destination exist:
- Same checksum: skip, mark "already present"
- Different checksum: deterministic rename `name__dup_<shorthash>.ext`

## Plan → Apply Workflow
1. `librarian plan` scans scatter, creates move plan in `state/pending.yaml`.
2. `librarian apply` executes moves, updates state/audit, reindexes, updates summary.
   - **Auto-timestamp**: Every move record MUST include UTC timestamp (`ts_utc`).
3. On success: remove from pending.
4. On failure: audit to `state/recent_changes.jsonl`, keep in pending.

## State Files (Canonical, Non-Core)
- `state/current_system.json` — machine state snapshot (auto-timestamped on updates)
- `state/pending.yaml` — moves plan + approval/errors
- `state/recent_changes.jsonl` — audit append-only (auto-timestamped on every append)
- `reports/summary/latest.md` — human "what's happening"
- `luka.md` — 30s dashboard (pointers + mode)

## Reindex Strategy
Reindex reports/**, memory/**, artifacts/**, state/**.
Do NOT full-text index logs/** (metadata or last N only).
