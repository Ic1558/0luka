# Antigravity Runtime Conformance Verification (2026-03-13)

## 1. Canonical reference

- `docs/architecture/adr/ADR-AG-001-antigravity-canonical-runtime.md`
- `docs/architecture/0LUKA_ARCHITECTURE_CONTRACT.md`
- `docs/architecture/0LUKA_LAYER_CONTRACT.md`
- `docs/architecture/ADR_INDEX.md`

## 2. Expected canonical runtime

Supervisor (allowed):
- launchd
- PM2

Entrypoint (canonical):
- `repos/option/modules/antigravity/realtime/control_tower.py`

Working directory:
- `repos/option`

Port:
- `8089`

Persistence:
- `modules/antigravity/realtime/artifacts/hq_decision_history.jsonl`

Endpoints:
- `/stream`
- `/api/status`
- `/api/contract`

## 3. Runtime verification summary

Verification timestamp:
- 2026-03-13 18:35 +0700

Supervisor detected:
- PM2 process online (`Antigravity-HQ`, launcher PID `97256`, python child PID
  `97282`)
- launchd label present (`com.antigravity.controltower`)

Process PID:
- launcher `97256`
- python child `97282`

Port binding:
- `8089` listening by PID `97282`

API verification:
- `curl http://127.0.0.1:8089/api/status` returned JSON payload
- `curl http://127.0.0.1:8089/api/contract` returned:
  `{"contract":"S50H26","sym":"S50H26.BK"}`

Decision history location:
- `modules/antigravity/realtime/artifacts/hq_decision_history.jsonl` exists

Entrypoint file verification:
- `repos/option/modules/antigravity/realtime/control_tower.py` not found on
  disk at verification time

Result classification:
- Major drift

## 4. Drift analysis

Observed mismatches against canonical contract:

1. Entrypoint mismatch:
   - running process args reference
     `modules/antigravity/realtime/control_tower.py`
   - on-disk entrypoint file was not present during verification
2. Supervision ambiguity:
   - PM2 runtime process was online while launchd label
     `com.antigravity.controltower` was also present
   - canonical contract requires single live supervisor ownership at a time

Observed matches:

1. Working directory matched (`/Users/icmini/0luka/repos/option`)
2. Port `8089` was bound and listening
3. Runtime API endpoints responded
4. Decision history artifact existed

## 5. Incident link

This verification is linked to incident classification:
- Architecture Drift + Credential Pairing Mismatch

Historical runtime confirmation remains valid. Current verification captures
present runtime wiring drift only.

## 6. Governance statement

This document records evidence-only runtime conformance status against the
canonical architecture contract ratified in ADR-AG-001. It does not modify
runtime state.
