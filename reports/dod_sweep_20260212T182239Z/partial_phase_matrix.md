# Global Partial Phase Matrix

- Source report: `reports/dod_sweep_20260212T182239Z/dod_checker_all.json`
- dod_checker exit code: `3`

## Summary Counts

| Verdict | Count |
|---|---:|
| PROVEN | 0 |
| PARTIAL | 12 |
| DESIGNED | 4 |

## Root-Cause Classes

- A) Missing required files: `0` phase(s)
- B) Registry mismatch (`registry.verdict_without_artifact`): `12` phase(s)
- C) Template drift (`governance.blueprint_schema_mismatch`): `0` phase(s)
- D) Evidence/activity not generated (`activity.*` / `evidence.*`): `16` phase(s)
- E) Governance lock violations: `0` (from `governance_lock_verify.json`)

## Non-PROVEN Matrix

| Phase | Verdict | Reason codes | Required missing items | File paths to touch |
|---|---|---|---|---|
| PHASE_10 | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_11 | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_15_3 | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_15_4 | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_15_5_0 | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_15_5_1 | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_15_5_2 | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_15_5_3 | DESIGNED | `activity.completed, activity.started, activity.verified` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl` | `observability/logs/activity_feed.jsonl` |
| PHASE_15_5_4 | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_1B | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_2 | DESIGNED | `activity.completed, activity.started, activity.verified` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl` | `observability/logs/activity_feed.jsonl` |
| PHASE_3E | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_8 | DESIGNED | `activity.completed, activity.started, activity.verified` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl` | `observability/logs/activity_feed.jsonl` |
| PHASE_9 | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |
| PHASE_DEMO_PROVEN | DESIGNED | `activity.completed, activity.started, activity.verified` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl` | `observability/logs/activity_feed.jsonl` |
| PHASE_OPS | PARTIAL | `activity.completed, activity.started, activity.verified, registry.verdict_without_artifact` | Add started/completed/verified chain to `observability/logs/activity_feed.jsonl`; Set valid `evidence_path` for PROVEN node in `core/governance/phase_status.yaml` | `observability/logs/activity_feed.jsonl`, `core/governance/phase_status.yaml`, `core/governance/governance_lock_manifest.json` |

## Remediation Order

1. Class D: generate deterministic activity chains for all non-fixture phases.
2. Class B: reconcile registry evidence paths via `dod_checker --all --update-status` loop until all phases PROVEN.
3. Re-verify lock manifest + growth guard + tests after each class commit.
