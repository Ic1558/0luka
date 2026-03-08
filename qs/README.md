# qs application layer scaffold

`qs` is the domain application layer for estimating/compliance/procurement workflows.
`0luka` remains the sealed runtime, governance, and control-plane layer.

## Separation of responsibility

- **qs domain logic** (`qs/domain/*`): deterministic business rules and ID generation.
- **qs contracts** (`qs/app/jobs.py`): application job contracts and lifecycle states.
- **qs adapter boundaries** (`qs/integration/*`): explicit interfaces for queue submit, approval check, and status publish into 0luka.

## Integration points (current)

- `OlukaQueueAdapter.submit_job(contract)`
- `OlukaPolicyAdapter.check_approval(contract)`
- `OlukaStatusAdapter.publish_status(payload)`

All adapters currently **fail closed by default** until wired to concrete 0luka interfaces.

## Approval-aware boundary

`qs/app/status.py` classifies each action as:

- `safe_read_only`
- `approval_required`
- `publish_finalize`

`po_generate` is marked `requires_approval=True` in job contracts.

## What is stubbed vs real

- **Real now:** deterministic contracts, domain IDs, action-boundary classification, deterministic status payload shape, fail-closed adapter behavior.
- **Stubbed now:** transport wiring to 0luka runtime queue, real approval backend checks, and status publishing channels.
