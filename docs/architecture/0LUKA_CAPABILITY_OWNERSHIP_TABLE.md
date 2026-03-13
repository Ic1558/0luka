# 0LUKA Capability Ownership Table

| Capability | Canonical Owner | Layer | Execution Owner | Evidence Source | Change Authority |
|---|---|---|---|---|---|
| Operator Control | docs/architecture/capabilities/operator_control.md | Interface | interface/operator/ | Mission Control views, operator reports | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Policy Governance | docs/architecture/capabilities/policy_governance.md | Core | core/ | policy metrics, policy ledgers, review surfaces | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Decision Infrastructure | docs/architecture/capabilities/decision_infrastructure.md | Core | core/ | decision history, decision ledgers | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Runtime Execution | docs/architecture/capabilities/runtime_execution.md | Runtime | runtime/ | runtime health, execution outcomes, reconciliation logs | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Observability Intelligence | docs/architecture/capabilities/observability_intelligence.md | Observability | observability/ | logs, artifacts, reports, ledgers | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Agent Execution | docs/architecture/capabilities/agent_execution.md | System / Services | agents/ | agent outputs, execution traces, audit logs | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |
| Antigravity Module | docs/architecture/capabilities/antigravity_module.md | Module | modules/antigravity/ | domain logs, alerts, artifacts | docs/architecture/0LUKA_ARCHITECTURE_DECISION_RECORDS.md |

## Ownership Rules

1. Every capability has exactly one canonical owner.
2. Execution owner may differ from canonical owner, but must not redefine ownership.
3. Evidence source must remain append-only or auditable.
4. Change authority must be explicit.
5. No secondary document may redefine the same capability as canonical.

## Interpretation Notes

- Canonical Owner = source of truth
- Execution Owner = runtime component that actually performs work
- Evidence Source = where the system proves behavior
- Change Authority = who may approve structural changes
