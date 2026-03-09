# 0LUKA Platform Freeze v1

## Status

- freeze_id: `0luka-platform-v1`
- state: `PARTIAL_FREEZE_ACTIVE`
- mode: `FAIL_CLOSED`
- date_utc: `2026-03-09`

## Purpose

This freeze records the current verified 0luka platform baseline so that runtime, observability, and QS application interfaces do not drift while Tier 2 closure continues.

This freeze does not claim full platform seal yet.

## What Is Frozen

The following interfaces are treated as frozen for v1:

- `run_registered_job(job_type, context)`
- `artifact_refs` return contract
- `runtime_root/state/qs_runs/<run_id>.json`
- `/api/qs_runs`
- `/api/qs_runs/{run_id}`
- append-only `activity_feed` chain
- activity feed action/run_id index contract
- `tools/ops/runtime_validator.py` report/mode contract
- `tools/ops/runtime_guardian.py` safe action contract

Canonical machine-readable source:

- `core/governance/0luka_platform_frozen_manifest.yaml`

## What Is Not Frozen

The following remain open:

- baseline git tag creation
- full system-wide Mission Control closure
- full-platform validator coverage outside QS scope
- destructive or broad guardian recovery behavior
- multi-engine platform rollout

## Compatibility Rules

Allowed without major bump:

- additive fields
- additive diagnostics
- additive operator views

Not allowed without major bump:

- interface removal
- identity field rewrite
- artifact contract shape break
- semantic redefinition of QS projection fields
- runtime path bypass

## Required Change Control

Any change affecting frozen interfaces must include:

- ADR
- proof-backed tests
- documentation update
- explicit compatibility note

## Current Evidence Anchor

Current evidence is anchored by:

- `docs/0LUKA_MASTER_DOD_CHECKLIST.md`
- `docs/review/QS_v1_VERIFIED.md`
- `core/verify/test_runtime_validator.py`
- `core/verify/test_runtime_guardian.py`
- `core/verify/test_activity_feed_guard_evidence.py`
- `core/verify/test_activity_feed_index_evidence.py`
- `core/verify/test_pack10_index_sovereignty.py`
- `core/verify/test_mission_control_feed_consumption.py`
- `core/verify/test_mission_control_summary_feed.py`
- `core/verify/test_qs_mission_control_projection.py`

## Remaining Gap To Full Seal

This freeze remains partial until:

1. a platform baseline tag is created
2. freeze evidence is anchored to that tag
3. contractual freeze list is accepted as canonical governance input

## Summary

0luka platform v1 is now frozen in-repo at the contract and documentation layer.

The freeze is active enough to prevent drift in proven interfaces, but it is not yet a fully sealed baseline until the git/tag anchor is created.
