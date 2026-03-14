"""Antigravity state writeback scaffolding.

Contract-aligned writeback interface only.
No file I/O, no persistence, no subprocess, and no live runtime mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Union

from runtime.antigravity.runtime_state.antigravity_runtime_state import (
    AntigravityRuntimeState,
)


@dataclass
class StateWritebackRequest:
    """Writeback request envelope for future approved persistence work."""

    state: AntigravityRuntimeState
    target_path: str
    write_mode: str = "contract_only"


@dataclass
class StateWritebackResult:
    """Writeback validation outcome at scaffold stage."""

    allowed: bool
    reason: str
    target_path: str


class AntigravityStateWriteback:
    """Contract-aligned writeback scaffold.

    This scaffold does not write data. It only validates and projects payloads
    in memory until a later approved persistence implementation is introduced.
    """

    def validate_request(self, request: StateWritebackRequest) -> StateWritebackResult:
        return StateWritebackResult(
            allowed=False,
            reason=(
                "state writeback persistence is not implemented; "
                "requires a later approved implementation PR"
            ),
            target_path=request.target_path,
        )

    def preview_payload(
        self, state: AntigravityRuntimeState
    ) -> Dict[str, Union[str, List[str]]]:
        return {
            "phase": state.phase.value,
            "approval_state": state.approval_state.value,
            "blockers": list(state.blockers),
            "evidence_refs": list(state.evidence_refs),
            "working_directory": state.working_directory,
            "canonical_entrypoint": state.canonical_entrypoint,
        }
