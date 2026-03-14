"""Kernel-owned protected boundary metadata."""

from __future__ import annotations

from fnmatch import fnmatch

KERNEL_BOUNDARIES: dict[str, list[str]] = {
    "runtime_state": [
        "core.runtime.runtime_state_resolver.RuntimeStateResolver",
        "runtime.runtime_service.RuntimeService.get_runtime_state_resolver",
    ],
    "policy": [
        "core.policy.*",
        "core.runtime.get_active_policy",
    ],
    "execution_bridge": [
        "core.task_dispatcher.*",
        "tools.bridge.*",
    ],
    "observability": [
        "observability.*",
        "core.runtime.runtime_event_writer.*",
    ],
}


def get_kernel_boundaries() -> dict[str, list[str]]:
    return {capability: list(routes) for capability, routes in KERNEL_BOUNDARIES.items()}


def is_allowed_boundary_access(capability: str, import_path: str) -> bool:
    allowed = KERNEL_BOUNDARIES.get(capability, [])
    return any(fnmatch(import_path, pattern) for pattern in allowed)

