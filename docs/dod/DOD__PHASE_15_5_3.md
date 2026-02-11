# DoD — PHASE_15_5_3

## Metadata & Revision History
- **Version**: v1.0
- **Edited By**: Codex (Librarian)
- **Date**: 2026-02-11
- **Reason**: Wire Phase 15.5.3 idle/drift monitor into Tier1 DoD governance.

## 0. Metadata (MANDATORY)
- **Phase / Task ID**: PHASE_15_5_3
- **Owner (Actor)**: ops-monitor
- **Gate**: G1
- **Related SOT Section**: §Tier1.Phase15.5.3
- **Target Status**: DESIGNED → PARTIAL → PROVEN
- **Commit SHA**: 61dfac8c3a6018f0ee28695d98688978d403e916
- **Date**: 2026-02-11

---

## 4. Evidence (Fail-Closed Core)
- [ ] Activity event: `started`
- [ ] Activity event: `completed`
- [ ] Activity event: `verified`
- [ ] `observability/reports/idle_drift_monitor/idle_drift.latest.json` exists and is readable
- [ ] `missing[] == []` for PROVEN run
- [ ] `missing[]` does not include `error.log_parse_failure`

### Notes / Links (Evidence pointers)
- **Spec**: `modules/ops/phase15_5_3/SPEC.md`
- **Tool**: `tools/ops/idle_drift_monitor.py`
- **Report Directory**: `observability/reports/idle_drift_monitor/`
- **Primary Proof File**: `observability/reports/idle_drift_monitor/idle_drift.latest.json`
- **Source Log Resolution**:
  - env `LUKA_ACTIVITY_FEED_JSONL`
  - fallback `observability/logs/activity_feed.jsonl`
- **Threshold Notes**:
  - `LUKA_IDLE_THRESHOLD_SEC` (default: 900)
  - `LUKA_DRIFT_THRESHOLD_SEC` (default: 120)
- **Verification Commands**:
  - `python3 tools/ops/idle_drift_monitor.py --once --json`
  - `python3 tools/ops/dod_checker.py --phase PHASE_15_5_3 --json`
