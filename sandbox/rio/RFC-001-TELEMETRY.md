# RFC-001: Telemetry Topology Consolidation

## Status
DRAFT | REVIEW | **ACCEPTED** | REJECTED
**Implemented At**: Commit `3273dbc`

---
*Proposed by*: `[Rio]`
*Reviewed by*: `[Liam]`
*Decided by*: `[GMX]`

## 1. Problem Statement
The 0luka system currently has multiple telemetry roots emerging from different development phases:
1. `0luka/g/telemetry` (Legacy/Bridge)
2. `0luka/observability/telemetry` (Governance v2.0)
3. `0luka/system/tools/telemetry` (Internal Tools)

This fragmentation complicates forensic audits and cross-agent log correlation.

## 2. Proposed Solution
Consolidate all telemetry output into a single, authoritative hierarchy under `observability/`:

```
observability/
├── telemetry/          # JSONL Forensic Logs
│   ├── liam.jsonl
│   ├── lisa.jsonl
│   ├── vera.jsonl
│   └── gate_emergency.jsonl
├── traces/             # Full task traces (v1.7.0 style)
└── metrics/            # System health metrics (Future)
```

### Migration Plan:
- Update `system/agents/_base_agent.py` to point to the new canonical root.
- Update `tools/bridge/consumer.py` for emergency log output.
- Symbolic links from legacy paths to ensure zero-break transition.

## 3. Governance Impact
- **Forensic Integrity**: Simplifies `Vera` audit logic as she only needs to watch one root.
- **Role Isolation**: No change to permissions; just path normalization.

## 4. Risks
- Broken paths in legacy scripts (mitigated by symlinks).
- Log rotation script updates required.

## 5. Verification
- **Log Routing**: Verify that `[Vera]` or `[Lisa]` logs successfully append to `observability/telemetry/*.jsonl`.
- **Symlink Check**: `ls -l g/telemetry` must point to `observability/telemetry`.
- **Real Dir Guard**: Verify `g/telemetry` is not a physical directory.

## 6. Rollback
- **Procedure**: If symlink failure occurs, remove symlinks and restore physical directories.
- **Data Integrity**: Sync `observability/telemetry/*.jsonl` back to old roots before restoration.
