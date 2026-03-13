# Antigravity Runtime State

This directory reserves runtime state-model scaffolding for approved future
execution work.

## Role

- define local runtime state abstractions
- support evidence and phase tracking without live mutation
- provide typed model in `antigravity_runtime_state.py` for executor linkage
- provide contract-aligned writeback scaffold in `state_writeback.py`
- follow `docs/architecture/runtime/ANTIGRAVITY_STATE_WRITEBACK_CONTRACT.md`
  for future persistence boundaries

## Non-goals

- no persistence migration
- no persistence implementation yet
- no writeback implementation yet (scaffold validation/projection only)
- no live runtime state override
