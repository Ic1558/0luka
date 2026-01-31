# RFC-002: Sovereign Core v1.1 Scope

## Status
**DRAFT** | REVIEW | ACCEPTED | REJECTED

---
*Proposed by*: `[Rio]`

## 1. Objective
Define the functional and governance expansion for the next iteration (v1.1) of the 0luka Sovereign Core.

## 2. Proposed Scope
The following items are proposed for inclusion in v1.1:

### A. Integrated Validation Chain
- Automatic invocation of `Vera` (Base) and `Vera-QS` upon `Lisa` execution.
- GMX Approval Gate UI integration via Raycast.

### B. Telemetry Normalization
- Implementation of RFC-001 (Consolidated Telemetry Root).
- Structured Trace IDs across all logs (correlation logic).

### C. Agent Skill Expansion
- **Liam**: Template-based RFC generation for sandbox experiments.
- **Rio**: Shared memory access for R&D historical analysis.

## 3. Security Considerations
- Ensure the v1.0 `_base_agent.py` remains the immutable root of trust.
- All v1.1 changes must be implemented as non-breaking extensions.

## 4. Next Steps
- Review by `[GMX]` and `[Liam]`.
- Approval of Scope.
