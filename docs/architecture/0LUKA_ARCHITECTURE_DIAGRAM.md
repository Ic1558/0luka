# 0LUKA Architecture Diagram

## Layer + Capability View

```text
+------------------------------------------------------+
| Interface Layer                                      |
|------------------------------------------------------|
| Capability: Operator Control                         |
| Canonical Doc: capabilities/operator_control.md      |
| Execution: interface/operator/                       |
+------------------------------------------------------+
                      |
                      v
+------------------------------------------------------+
| Module Layer                                         |
|------------------------------------------------------|
| Capability: Antigravity Module                       |
| Canonical Doc: capabilities/antigravity_module.md    |
| Execution: modules/antigravity/                      |
+------------------------------------------------------+
                      |
                      v
+------------------------------------------------------+
| System / Services Layer                              |
|------------------------------------------------------|
| Capability: Agent Execution                          |
| Canonical Doc: capabilities/agent_execution.md       |
| Execution: agents/                                   |
+------------------------------------------------------+
                      |
                      v
+------------------------------------------------------+
| Runtime Layer                                        |
|------------------------------------------------------|
| Capability: Runtime Execution                        |
| Canonical Doc: capabilities/runtime_execution.md     |
| Execution: runtime/                                  |
+------------------------------------------------------+
                      |
                      v
+------------------------------------------------------+
| Core Layer                                           |
|------------------------------------------------------|
| Capability: Policy Governance                        |
| Canonical Doc: capabilities/policy_governance.md     |
| Execution: core/                                     |
|                                                      |
| Capability: Decision Infrastructure                  |
| Canonical Doc: capabilities/decision_infrastructure.md |
| Execution: core/                                     |
+------------------------------------------------------+
                      |
                      v
+------------------------------------------------------+
| Observability Layer                                  |
|------------------------------------------------------|
| Capability: Observability Intelligence               |
| Canonical Doc: capabilities/observability_intelligence.md |
| Execution: observability/                            |
+------------------------------------------------------+
```

## Dependency Direction

Interface
  -> System / Services
  -> Runtime
  -> Core
  -> Observability

Forbidden examples:

- Core -> Runtime
- Core -> Interface
- Runtime -> Interface
- Observability -> Runtime

## Governance Flow View

Operator Control
        |
        v
Decision Infrastructure
        |
        v
Policy Governance
        |
        v
Runtime Execution
        |
        v
Observability Intelligence

## Notes

- Interface is optional for system survival.
- Modules provide domain intelligence, not system governance.
- Runtime executes governed actions only.
- Core defines law, policy, and decisions.
- Observability records evidence and does not control execution.
