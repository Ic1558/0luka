# ADR-004: Domain Engine Extension Model

## Status

Accepted

## Context

0luka is intended to support multiple domain engines.

Possible engines include:
- QS
- AEC
- Finance
- Document processing
- AI analysis

The architecture must allow new engines without modifying the runtime kernel.

## Decision

Domain logic will be implemented as domain engines under:

`repos/<engine_name>/`

Engines must integrate using the runtime interface:

`run_registered_job(job_type, context)`

Runtime kernel must remain independent from domain engines.

## Consequences

Benefits:
- clean separation of concerns
- extensible platform
- stable runtime kernel

Trade-offs:
- slightly more complex integration

## Alternatives Considered

Embedding domain logic inside core runtime:
- Rejected because it couples business logic to kernel behavior and reduces platform extensibility.
