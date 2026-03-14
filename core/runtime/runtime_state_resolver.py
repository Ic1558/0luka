"""Authoritative runtime state path resolver."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def resolve_runtime_root(runtime_root: Optional[Path | str] = None) -> Path:
    raw = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT") or os.environ.get("RUNTIME_ROOT")
    if not raw or not str(raw).strip():
        raise RuntimeError("runtime_root_missing")
    root = Path(str(raw)).expanduser().resolve()
    if not root.exists():
        raise RuntimeError(f"runtime_root_not_found:{root}")
    return root


class RuntimeStateResolver:
    """Expose canonical runtime state paths from a single authority layer."""

    def __init__(self, runtime_root: Path):
        if runtime_root is None:
            raise RuntimeError("runtime_root_missing")
        if not runtime_root.exists():
            raise RuntimeError(f"runtime_root_not_found:{runtime_root}")
        self.runtime_root = runtime_root.resolve()

    @classmethod
    def from_runtime_root(
        cls, runtime_root: Optional[Path | str] = None
    ) -> "RuntimeStateResolver":
        return cls(resolve_runtime_root(runtime_root))

    def state_dir(self) -> Path:
        return self.runtime_root / "state"

    def path_in_state(self, *parts: str) -> Path:
        return self.state_dir().joinpath(*parts)

    def qs_runs_dir(self) -> Path:
        return self.path_in_state("qs_runs")

    def current_system_file(self) -> Path:
        return self.path_in_state("current_system.json")

    def alerts_file(self) -> Path:
        return self.path_in_state("alerts.jsonl")

    def approval_actions_file(self) -> Path:
        return self.path_in_state("approval_actions.jsonl")

    def approval_log_file(self) -> Path:
        return self.path_in_state("approval_log.jsonl")

    def remediation_history_file(self) -> Path:
        return self.path_in_state("remediation_history.jsonl")

    def system_model_file(self) -> Path:
        return self.path_in_state("system_model.json")
