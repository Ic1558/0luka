# RFC-001: Telemetry Topology Consolidation (Consolidated)

## 1. Proposal Details
> [!NOTE]
> This section is consolidated from the original proposal at `sandbox/rio/RFC-001-TELEMETRY.md`.

### Status
DRAFT | REVIEW | **ACCEPTED** | REJECTED
**Implemented At**: Commit `3273dbc`

---
*Proposed by*: `[Rio]`
*Reviewed by*: `[Liam]`
*Decided by*: `[GMX]`

### 1.1 Problem Statement
The 0luka system currently has multiple telemetry roots emerging from different development phases:
1. `0luka/g/telemetry` (Legacy/Bridge)
2. `0luka/observability/telemetry` (Governance v2.0)
3. `0luka/system/tools/telemetry` (Internal Tools)

> [!NOTE]
> The directory `./telemetry/` is **documentation-only** (contains `schema.md`). All telemetry outputs are strictly consolidated into `observability/telemetry/`.

This fragmentation complicates forensic audits and cross-agent log correlation.

### 1.2 Proposed Solution
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

### 1.3 Migration Plan
- Update `system/agents/_base_agent.py` to point to the new canonical root.
- Update `tools/bridge/consumer.py` for emergency log output.
- Symbolic links from legacy paths to ensure zero-break transition.

### 1.4 Governance Impact
- **Forensic Integrity**: Simplifies `Vera` audit logic as she only needs to watch one root.
- **Role Isolation**: No change to permissions; just path normalization.

### 1.5 Risks
- Broken paths in legacy scripts (mitigated by symlinks).
- Log rotation script updates required.

### 1.6 Verification
- **Log Routing**: Verify that `[Vera]` or `[Lisa]` logs successfully append to `observability/telemetry/*.jsonl`.
- **Symlink Check**: `ls -l g/telemetry` must point to `observability/telemetry`.
- **Real Dir Guard**: Verify `g/telemetry` is not a physical directory.

---

## 2. Audit Verdict (Final)
> [!NOTE]
> This section is consolidated from the original verdict at `RFC-001.md` (root).

```yaml
verdict: PASS
scope: telemetry_consolidation
canonical_root: observability/telemetry
runtime_verified: true
retention_verified: true
action_required: none
auditor: GMX
timestamp: 2026-02-01
```

### 2.1 Meta-Audit
```yaml
meta_audit:
  markdown_fences: clean
  yaml_blocks: valid
  section_numbering: sequential
  editor_method: cli
  remediation: truncate_and_rewrite
  confidence: high
reviewed_by: GMX
timestamp: 2026-02-01
```

---
## 3. Legacy References
- Original Proposal: `docs/rfc/legacy/RFC-001-TELEMETRY.md.legacy`
- Original Verdict: `docs/rfc/legacy/RFC-001.md.legacy`
