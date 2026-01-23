# 0luka Source of Truth (S.O.T.) Protocol v1.0

## 1. Core Principles
- **Local Consistency:** Workspace Artifacts are the primary source of truth for execution.
- **External Integration (MCP):** Google Tasks and other external managers act as "Live Intent" sources.

## 2. Synchronization Standards
- All external intents must be converted to local `TASKLIST.md` artifacts.
- Execution status must be promoted back to external managers only after local verification (PRP).

## 3. File Standards
- Filenames must start with `yymmdd_` for time-series integrity.
- Never overwrite critical policies: backup old -> replace with new.
- Keep max 2 backups per file.
