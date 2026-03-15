"""AG-18: DecisionRecord — minimal serializable decision model. No IO, no side effects."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionRecord:
    decision_id: str
    ts_utc: str
    source_run_id: str
    classification: str
    action: str
    confidence: float
    policy_verdict: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "ts_utc": self.ts_utc,
            "source_run_id": self.source_run_id,
            "classification": self.classification,
            "action": self.action,
            "confidence": self.confidence,
            "policy_verdict": self.policy_verdict,
            "reason": self.reason,
        }

    @classmethod
    def make(
        cls,
        *,
        source_run_id: str,
        classification: str,
        action: str,
        confidence: float,
        policy_verdict: str = "PENDING",
        reason: str = "",
        ts_utc: str | None = None,
    ) -> "DecisionRecord":
        if ts_utc is None:
            ts_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        raw = f"{source_run_id}|{ts_utc}|{classification}|{action}"
        decision_id = "dec_" + hashlib.sha256(raw.encode()).hexdigest()[:12]
        return cls(
            decision_id=decision_id,
            ts_utc=ts_utc,
            source_run_id=source_run_id,
            classification=classification,
            action=action,
            confidence=float(confidence),
            policy_verdict=policy_verdict,
            reason=reason,
        )
