# Antigravity Runtime Scaffolding

This subtree defines canonical runtime scaffolding for future approved
Antigravity runtime work under `runtime/`.

## Boundaries

- This subtree is implementation-prep only.
- It does not authorize live runtime mutation by itself.
- It does not replace the current control tower runtime.
- Broker auth remains a separate ops lane.
- Artifact models under `artifacts/` are analysis-layer only.
- Worker scaffold at `worker/runtime_worker.py` is approval-gated stub only.

## Non-goals

- no PM2 integration
- no launchd integration
- no deployment behavior
