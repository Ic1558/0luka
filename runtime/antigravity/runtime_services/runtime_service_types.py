"""Runtime service contract types for Antigravity scaffolding.

These types define structure only. They contain no execution logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RuntimeArtifactReference:
    """Reference to an analysis/runtime artifact."""

    artifact_id: str
    artifact_type: str
    reference_path: str
    notes: str = ""


@dataclass
class RuntimeServiceContext:
    """Context passed to runtime service handlers."""

    runtime_id: str
    phase: str
    approval_state: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeExecutionRequest:
    """Unified request object for runtime service calls."""

    service_name: str
    action: str
    context: RuntimeServiceContext
    payload: Dict[str, Any] = field(default_factory=dict)
    artifact_refs: List[RuntimeArtifactReference] = field(default_factory=list)


@dataclass
class RuntimeExecutionResult:
    """Unified result object for runtime service calls."""

    accepted: bool
    status: str
    message: str = ""
    artifact_refs: List[RuntimeArtifactReference] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
