# Kernel Boundary Enforcement

## Rule
Protected capabilities must be accessed only through kernel-owned boundary APIs.
This enforcement is detection-only.
It does not redesign runtime behavior.

## Protected capabilities
- `runtime_state`
- `policy`
- `execution_bridge`
- `observability`

## Allowed authority examples
- `core.runtime.runtime_state_resolver.RuntimeStateResolver`
- `runtime.runtime_service.RuntimeService.get_runtime_state_resolver`
- `core.task_dispatcher.*`
- `tools.bridge.*`
- approved policy modules under `core.policy.*`

## Forbidden patterns
- ad hoc direct runtime state path building outside boundary owners
- direct policy state file access outside policy/boundary owners
- direct bridge import coupling outside approved bridge/dispatcher owners
- bypassing boundary APIs with local direct routing shortcuts

## Enforcement points
- Pytest: `core/verify/test_kernel_boundary_guard.py`
- Pre-commit: `tools/guards/check_kernel_boundaries.py`
- CI: `.github/workflows/no-machine-paths.yml`
