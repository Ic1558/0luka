# Antigravity Runtime Remediation Plan (2026-03-13)

## Canonical references

- `adr/ADR-AG-001-antigravity-canonical-runtime.md`
- `antigravity/ANTIGRAVITY_ARCHITECTURE_CONTRACT.md`
- `antigravity/ANTIGRAVITY_DRIFT_CLASSIFICATION.md`
- `antigravity/ANTIGRAVITY_RUNTIME_RECOVERY_RUNBOOK.md`
- `runtime/ANTIGRAVITY_RUNTIME_CONFORMANCE_2026-03-13.md`

## Proven drift

Evidence-backed drift from runtime conformance:

- dual-supervisor signal was observed
- entrypoint reference was present in process args
- on-disk entrypoint file was missing at verification time
- runtime still served API responses
- history artifact remained present

## Remediation objective

Target end-state:

- exactly one live supervisor owner
- canonical maintained on-disk entrypoint
- working directory remains canonical
- history artifact path remains unchanged
- broker auth remains separately classified

## Remediation phases

### Phase 1 - Supervisor ownership decision

- choose launchd or PM2 as the single live owner
- classify the other as historical or disabled

### Phase 2 - Entrypoint restoration or canonical repoint

- either restore the maintained entrypoint on disk
- or formally repoint runtime command to a maintained canonical wrapper/path
- do not treat stale process state as source truth

### Phase 3 - Runtime verification

- verify port health
- verify API endpoint responses
- verify history artifact presence
- verify process args
- verify single-supervisor state

### Phase 4 - Broker auth remains separate

- do not mix credential pairing repair into runtime remediation acceptance

## Acceptance criteria

- one supervisor only
- maintained entrypoint exists on disk
- process args match canonical path
- port 8089 healthy
- `/api/status` responds
- `/api/contract` responds
- history artifact preserved
- broker auth classified separately

## Non-goals

- no broker auth fix in this plan
- no runtime feature work
- no UI redesign
- no trading logic changes

## Governance note

This document is planning-only and does not authorize runtime mutation by
itself.
