# Remediation Plan: Activity Feed Corruption

## 1. Objective
Resolve `error.log_parse_failure` in Phase 15.5.3 by sanitizing the activity feed while maintaining a full audit trail and absolute reversibility.

## 2. Evidence of Failure (Forensics)
Run the forensics playbook to identify the scope of corruption:
```bash
zsh tools/ops/forensics_jsonl.zsh
```
*Criteria*: If bad lines are found, proceed to remediation.

## 3. Remediation Logic (Fail-Closed)
We use `tools/ops/activity_feed_fix.py` to perform the following atomic operations:
1.  **Integrity Capture**: Compute SHA256 of the corrupt file.
2.  **Quarantine**: Copy the corrupt file to `observability/quarantine/activity_feed/<ts>_activity_feed.jsonl`.
3.  **Filtration**: Extract only valid JSON lines into memory.
4.  **Atomic Replace**: Overwrite the original `observability/logs/activity_feed.jsonl` with the sanitized content.
5.  **Audit Report**: Generate a machine-readable JSON report in `observability/reports/activity_feed_fix/` documenting the SHA changes and samples of dropped content.

## 4. Reversal Procedure
If data loss is deemed unacceptable:
```bash
cp <quarantine_path> observability/logs/activity_feed.jsonl
```

## 5. Verification of Done (PHASE_15_5_3)
1.  **Monitor Reset**: `python3 tools/ops/idle_drift_monitor.py --json` should return `missing=[]` (assuming recent activity exists).
2.  **Heartbeat Emission**: Inject a valid heartbeat to the feed.
3.  **DoD Assertion**: `python3 tools/ops/dod_checker.py --phase PHASE_15_5_3 --json` computes **PROVEN**.
