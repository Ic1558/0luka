"""Antigravity runtime service unification scaffolding."""

from .runtime_service_registry import (
    get_service,
    list_services,
    register_service,
)
from .runtime_service_types import (
    RuntimeArtifactReference,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
    RuntimeServiceContext,
)

__all__ = [
    "RuntimeArtifactReference",
    "RuntimeExecutionRequest",
    "RuntimeExecutionResult",
    "RuntimeServiceContext",
    "register_service",
    "get_service",
    "list_services",
]
