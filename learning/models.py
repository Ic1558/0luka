"""AG-21: Learning plane data models.

Pure data containers — no IO, no side effects.
Serializable to/from dict for JSONL storage.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ObservationRecord:
    """One complete execution cycle observation."""
    run_id: str
    decision_id: str = ""
    plan_id: str = ""
    execution_result: str = ""   # SUCCESS | FAILED | PARTIAL | NO_OP
    verifier_status: str = ""    # SUCCESS | FAILED | PARTIAL
    adaptation_result: str = ""  # STOP | RETRY | SAFE_FALLBACK | ESCALATE
    policy_verdict: str = ""     # ALLOW | BLOCK | ESCALATE
    timestamp: str = ""
    observation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ObservationRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PatternRecord:
    """A recurring pattern detected in observation history."""
    pattern_id: str
    pattern_type: str            # repeated_executor_failure | repeated_policy_block | ...
    trigger_conditions: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0      # 0.0 – 1.0
    observation_count: int = 0   # number of supporting observations

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PatternRecord":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PolicyCandidate:
    """An operator-reviewable policy candidate derived from a pattern.

    AG-21 may only create candidates (approval_state=PENDING).
    Promotion/activation is AG-22 territory.
    """
    candidate_id: str
    pattern_id: str
    suggested_policy: str        # human-readable policy suggestion
    safety_risk: str = "low"     # low | medium | high
    approval_state: str = "PENDING"  # PENDING only in AG-21

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PolicyCandidate":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
