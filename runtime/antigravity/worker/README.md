# Antigravity Runtime Worker

This directory reserves worker-process scaffolding for future approved runtime
execution.

## Role

- host task worker abstractions
- isolate worker responsibilities from executor orchestration
- provide approval-gated stub via `runtime_worker.py`

## Non-goals

- no live worker deployment
- no service lifecycle integration
- no subprocess execution
- no live runtime mutation
