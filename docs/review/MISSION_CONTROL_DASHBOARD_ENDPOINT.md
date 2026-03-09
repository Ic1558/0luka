# Mission Control Dashboard Endpoint

## Endpoint
`GET /api/operator/dashboard`

## Purpose
This endpoint provides a unified, single-request projection of the entire 0luka operator dashboard state. It aggregates data from both kernel and operator read surfaces to minimize frontend latency and polling overhead.

## Response Schema
```json
{
  "kernel": { ... },
  "verification": [ ... ],
  "guardian": [ ... ],
  "runtime_decisions": [ ... ],
  "remediation_queue": [ ... ],
  "approval_state": { ... },
  "policy_drift": { ... },
  "qs_overview": {
    "summary": { ... },
    "recent_items": [ ... ]
  }
}
```

## Determinism Guarantees
- **Decision Log**: Capped at 50 most recent entries, reverse-chronological.
- **QS Overview**: Aggregated counts plus top 20 recent items based on alphabetical state-file sorting.
- **Stable Keys**: All top-level and nested keys are mapped from frozen Phase D/E contracts.

## Safety Guarantees
- **Read-Only Aggregation**: The endpoint combines outputs from purely passive loaders. It does not trigger dispatcher cycles, writes, or state mutations.
- **Safe Degradation**: If any individual truth source (e.g., project state dir or remediation log) is missing or corrupted, the aggregator returns empty default structures for that panel rather than failing the entire request.
- **Method Enforcement**: Strictly GET-only.
