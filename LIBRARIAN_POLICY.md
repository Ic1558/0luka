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

## Scoring & Gates (Git-Gate Equivalent)

### 1) Scoring Model (0–100)
**Pass threshold**: 70

**Gate types**
| Gate | Score | Meaning |
|------|--------|---------|
| HARD FAIL | 0 | Block (no override in v1) |
| SOFT FAIL | 1–69 | Block |
| WARN | 70–89 | Allow + flag |
| OK | 90–100 | Allow |

### 2) Criteria & Weights (Per Action)
| Criterion | Weight | Hard Rule | Pass Condition |
|-----------|--------|-----------|----------------|
| Path compliance | 30 | Rule violation | Source/dest match scatter→canonical rules |
| Checksum discipline | 20 | Mismatch | SHA256 computed and compared |
| Non-core safety | 25 | Core touched | No `core/` or `core_brain/` touched |
| Atomicity | 15 | Non-atomic | Single rename/move, no partial state |
| Traceability | 10 | Missing ts_utc | UTC timestamp + audit to `recent_changes.jsonl` |

**Maximum**: 100

### 3) Score Output (Write Per Action)
**Append to** `state/recent_changes.jsonl`:
```json
{
  "ts_utc": "2026-01-30T19:45:00Z",
  "event": "librarian_action",
  "action_type": "move",
  "move_id": "src=abc123|dst=def456|sz=1024|mt=123456789|ino=1234",
  "score": 95,
  "breakdown": {
    "path_compliance": 30,
    "checksum_discipline": 20,
    "non_core_safety": 25,
    "atomicity": 15,
    "traceability": 5
  },
  "gate": "OK",
  "reason": "",
  "src_path": "src/...",
  "dst_path": "dst/...",
  "conflict_policy": "error"
}
```

**Update** `state/current_system.json`:
```json
{
  "librarian": {
    "last_score": 95,
    "last_run_ts_utc": "2026-01-30T19:45:00Z",
    "last_gate": "OK"
  }
}
```

**Failed actions**
- Write score audit entry
- Keep in `state/pending.yaml`
- Block further applies until resolved
