# Contributing to 0luka

Thank you for contributing to 0luka.

0luka is a deterministic runtime execution platform designed to safely run domain engines through a controlled execution pipeline.

Because this repository defines a runtime platform, contributions must follow strict architectural and operational guidelines.

This document explains:
- how to contribute code
- how to propose architectural changes
- how to add new engines
- how to submit pull requests

## Contribution Principles

All contributions must respect the core platform principles.

Deterministic Execution:
- all workloads must pass through the runtime execution pipeline.
- direct handler invocation or bypassing runtime control is not allowed.

Reference:
- `docs/0LUKA_EXECUTION_MODEL.md`

Artifact Truth:
- artifacts must originate from handlers and must remain immutable.

Reference:
- `docs/0LUKA_ARTIFACT_MODEL.md`

Fail-Closed Behavior:
- unknown jobs or invalid runtime states must fail safely.

Reference:
- `docs/0LUKA_KERNEL_INVARIANTS.md`

Observability:
- all runtime actions must produce observable events.

Reference:
- `docs/0LUKA_RUNTIME_VALIDATOR.md`

## Types of Contributions

Contributions typically fall into four categories.

Runtime Platform Improvements:
- changes to the runtime kernel.
- example areas: dispatcher, router, runtime state management, validator, guardian.
- these changes require careful architectural review.

Domain Engine Development:
- new engines or job handlers.
- examples: QS, AEC, Finance, Document processing.
- usually implemented under `repos/<engine_name>/`.

Reference:
- `docs/0LUKA_EXTENSION_MODEL.md`

Operator Tools:
- improvements to operational utilities.
- examples: `tools/`, `interface/`, Mission Control.

Documentation:
- updates to platform documentation.
- examples: architecture docs, developer guides, ADR records.

## Repository Structure

Before contributing, familiarize yourself with the repository layout.

```text
0luka/
│
├─ core/
│     runtime control plane
│
├─ repos/
│     domain engines
│
├─ interface/
│     operator interfaces
│
├─ tools/
│     operational utilities
│
├─ observability/
│     telemetry and logs
│
├─ docs/
│     platform specification
│
├─ runtime_root/
│     runtime data
│
└─ tests/
      system tests
```

Reference:
- `docs/0LUKA_REPOSITORY_STRUCTURE.md`

## Development Setup

Typical development workflow:
- clone repository
- create feature branch
- implement changes
- run tests
- submit pull request

Example:

```bash
git clone <repo>
cd 0luka
git checkout -b feature/my-change
```

## Adding a Domain Engine

To add a new engine:

Step 1:
- create engine directory: `repos/<engine_name>/`
- example: `repos/aec/`

Step 2:
- create job registry (for example `job_registry.py`)
- register deterministic job types
- example: `aec.model_generate`, `aec.material_quantify`, `aec.render_report`

Step 3:
- implement handlers under `handlers/`
- example: `model_generate.py`, `material_quantify.py`
- handlers must return valid `artifact_refs`

Reference:
- `docs/0LUKA_DEVELOPER_GUIDE.md`

Step 4:
- add tests for handler execution, artifact correctness, and runtime compatibility.

## Runtime Platform Changes

Changes to the runtime kernel require additional care.

Areas affected include:
- dispatcher
- router
- state machine
- approval gate
- validator
- guardian

Before submitting such changes:
1. Review architecture documentation.
2. Ensure runtime invariants remain valid.
3. Update documentation if behavior changes.

References:
- `ARCHITECTURE.md`
- `docs/0LUKA_STATE_MACHINE_SPEC.md`

## Architecture Changes

Major architectural changes must include an ADR (Architecture Decision Record).

Location:
- `docs/ADR/`

Example files:
- `ADR-006-worker-execution-model.md`
- `ADR-007-distributed-runtime.md`

## Code Quality Requirements

All contributions must follow these rules.

Deterministic Behavior:
- handlers must produce predictable results.

Clear Error Handling:
- errors must fail safely.

No Synthetic Artifacts:
- artifacts must correspond to actual files.

Runtime Compatibility:
- all handlers must integrate with the runtime execution pipeline.

## Testing Requirements

All contributions must include tests.

Types of tests:
- unit tests
- runtime integration tests
- artifact validation tests

Tests are located under:
- `tests/`

## Pull Request Process

Typical PR workflow:
1. Create feature branch.
2. Implement change.
3. Add tests.
4. Update documentation.
5. Submit PR.

Example:

```bash
git push origin feature/my-change
```

PR description should include:
- summary of change
- affected components
- test coverage
- documentation updates

## Review Process

Pull requests are reviewed for:
- architecture compliance
- runtime invariant preservation
- artifact integrity
- code clarity
- test coverage

PRs that violate runtime principles may be rejected.

## Security Considerations

Contributors must respect platform security rules.

Examples:
- no direct runtime state modification
- no artifact mutation
- no bypassing approval gates

Reference:
- `docs/SECURITY_MODEL.md`

## Documentation Updates

If a change modifies platform behavior, documentation must be updated.

Relevant documents include:
- `ARCHITECTURE.md`
- `docs/0LUKA_EXECUTION_MODEL.md`
- `docs/0LUKA_DEVELOPER_GUIDE.md`
- `docs/0LUKA_OPERATOR_GUIDE.md`

Documentation must remain consistent with system behavior.
