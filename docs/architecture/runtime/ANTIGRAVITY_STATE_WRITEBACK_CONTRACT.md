# Antigravity State Writeback Contract

## Purpose

Define the rules for runtime state persistence before any writeback
implementation exists.

## Scope

This contract covers persistence of `AntigravityRuntimeState` only.
It does not authorize execution.
It does not authorize live runtime mutation.

## Canonical state object

Reference:
- `runtime/antigravity/runtime_state/antigravity_runtime_state.py`

## Allowed persisted fields

Only fields already defined by the current state model are in scope:
- `phase`
- `approval_state`
- `blockers`
- `evidence_refs`
- `working_directory`
- `canonical_entrypoint`

## Non-goals

- no PM2 persistence
- no launchd persistence
- no broker credential persistence
- no secret storage
- no subprocess logs
- no artifact payload duplication unless separately approved

## Writeback location

Canonical writeback location is defined conceptually under:
- `runtime/antigravity/state/`

This contract defines the location boundary only. It does not implement storage.

## Write triggers

Allowed future triggers are conceptual only:
- after explicit approved state transition
- after runtime planning events
- after artifact resolution events

This document does not implement any trigger.

## Read/write boundaries

- writeback must be append-safe or overwrite-safe by contract
- writeback must not mutate live runtime behavior
- writeback must not become approval source of truth
- approval remains a governance layer, not a persistence side effect

## Safety rules

- no secrets
- no broker auth data
- no filesystem writes without explicit later approval
- persistence implementation must be separate from this contract

## Governance note

This document defines persistence law only.
Implementation requires a later approved PR.
