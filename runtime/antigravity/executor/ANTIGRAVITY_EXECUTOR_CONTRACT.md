# Antigravity Executor Contract

## Purpose

Define the executor boundary for Antigravity Phase R1 scaffolding.

## Allowed responsibilities

- load local contract metadata abstractions
- validate preconditions in non-mutating mode
- build supervised execution plan artifacts
- report blockers and evidence references

## Forbidden responsibilities

- no PM2 calls
- no launchd calls
- no deployment actions
- no live runtime mutation
- no broker credential mutation
- no external API calls

## Approval relationship

- Executor does not authorize execution by itself.
- Executor defaults to non-approved mode.
- Runtime mutation requires explicit approval record.

## Broker auth relationship

- Broker auth remains a separate ops lane.
- Executor output must not classify broker auth as runtime architecture success
  or failure.

## Relationship to future layers

- worker: executes approved units only in future phases
- scheduler: coordinates approved execution windows only in future phases
- runtime_api: exposes approved runtime interfaces only in future phases
