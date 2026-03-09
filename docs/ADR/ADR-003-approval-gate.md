# ADR-003: Approval-Gated Execution

## Status

Accepted

## Context

Some domain operations may have real-world consequences.

Examples:
- purchase orders
- financial transactions
- contract documents

These operations must not execute automatically.

## Decision

The runtime platform introduces an approval gate.

Execution states include:
- `pending_approval`
- `approved`
- `rejected`

Handlers cannot execute until approval is granted.

## Consequences

Benefits:
- operational safety
- human oversight
- controlled execution

Trade-offs:
- additional operational steps
- approval management overhead

## Alternatives Considered

Fully automatic execution for all jobs:
- Rejected because it allows high-impact operations to run without operator control.
