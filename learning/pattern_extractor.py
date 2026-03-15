"""AG-21: Pattern extractor — detects recurring patterns in observation history.

Storage: $LUKA_RUNTIME_ROOT/state/pattern_registry.json

Rules:
  - reads observations only
  - does not mutate runtime behavior
  - deterministic extraction
  - MIN_OBSERVATIONS=3 before a pattern is confirmed
"""
from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from learning.models import PatternRecord
from learning.observation_store import get_recent_observations

_REGISTRY_NAME = "pattern_registry.json"

# Minimum supporting observations before a pattern is emitted
MIN_OBSERVATIONS: int = 3


def _registry_path() -> Path:
    import os
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(runtime_root) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d / _REGISTRY_NAME


def _load_registry() -> list[dict[str, Any]]:
    p = _registry_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_registry(patterns: list[dict[str, Any]]) -> None:
    p = _registry_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(patterns, indent=2), encoding="utf-8")
    tmp.replace(p)


def extract_patterns() -> list[PatternRecord]:
    """Scan recent observations and return detected patterns.

    Detects:
      repeated_executor_failure  — same execution_result=FAILED multiple times
      repeated_policy_block      — policy_verdict=BLOCK multiple times
      repeated_safe_fallback     — adaptation_result=SAFE_FALLBACK multiple times
      repeated_verification_partial — verifier_status=PARTIAL multiple times
    """
    observations = get_recent_observations(limit=200)
    if not observations:
        return []

    patterns: list[PatternRecord] = []

    # Count failure signals
    exec_failed = [o for o in observations if o.get("execution_result") == "FAILED"]
    policy_blocked = [o for o in observations if o.get("policy_verdict") == "BLOCK"]
    safe_fallbacks = [o for o in observations if o.get("adaptation_result") == "SAFE_FALLBACK"]
    verif_partial = [o for o in observations if o.get("verifier_status") == "PARTIAL"]

    for signal_obs, pattern_type, trigger_key in [
        (exec_failed, "repeated_executor_failure", "execution_result"),
        (policy_blocked, "repeated_policy_block", "policy_verdict"),
        (safe_fallbacks, "repeated_safe_fallback", "adaptation_result"),
        (verif_partial, "repeated_verification_partial", "verifier_status"),
    ]:
        if len(signal_obs) >= MIN_OBSERVATIONS:
            confidence = min(1.0, len(signal_obs) / max(len(observations), 1))
            patterns.append(PatternRecord(
                pattern_id=f"pattern_{uuid.uuid4().hex[:8]}",
                pattern_type=pattern_type,
                trigger_conditions={trigger_key: signal_obs[0].get(trigger_key, "")},
                confidence=round(confidence, 3),
                observation_count=len(signal_obs),
            ))

    return patterns


def update_pattern_registry() -> list[dict[str, Any]]:
    """Extract patterns and persist to registry. Returns updated registry."""
    new_patterns = extract_patterns()
    existing = _load_registry()

    # Merge: keep existing, add new types not already present
    existing_types = {p.get("pattern_type") for p in existing}
    for p in new_patterns:
        if p.pattern_type not in existing_types:
            existing.append(p.to_dict())
            existing_types.add(p.pattern_type)
        else:
            # Update observation_count and confidence for existing pattern
            for ep in existing:
                if ep.get("pattern_type") == p.pattern_type:
                    ep["observation_count"] = p.observation_count
                    ep["confidence"] = p.confidence
                    break

    _save_registry(existing)
    return existing


def get_patterns() -> list[dict[str, Any]]:
    """Return current pattern registry."""
    return _load_registry()
