"""AG-21: Policy candidates — generate operator-reviewable policy proposals.

Storage: $LUKA_RUNTIME_ROOT/state/policy_candidates.jsonl

Rules:
  - AG-21 may create candidates (approval_state=PENDING) only
  - NO policy activation in AG-21 — that is AG-22 territory
  - append-only log
  - atomic writes
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from learning.models import PolicyCandidate
from learning.pattern_extractor import get_patterns

_LOG_NAME = "policy_candidates.jsonl"

# Map pattern_type → suggested policy text + risk level
_PATTERN_TO_POLICY: dict[str, tuple[str, str]] = {
    "repeated_executor_failure": (
        "limit executor retry depth to 1 for the triggering plan type",
        "low",
    ),
    "repeated_policy_block": (
        "review policy rules blocking recurring action type — consider adding explicit ESCALATE rule",
        "medium",
    ),
    "repeated_safe_fallback": (
        "investigate root cause of repeated safe_fallback — consider tightening plan constraints",
        "low",
    ),
    "repeated_verification_partial": (
        "inspect artifact surface completeness for plans triggering partial verification",
        "low",
    ),
}


def _log_path() -> Path:
    import os
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(runtime_root) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d / _LOG_NAME


def append_candidate(candidate: PolicyCandidate | dict[str, Any]) -> dict[str, Any]:
    """Append one policy candidate to the log."""
    if isinstance(candidate, PolicyCandidate):
        data = candidate.to_dict()
    else:
        data = dict(candidate)
    if not data.get("ts"):
        data["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    log_path = _log_path()
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    tmp = log_path.with_suffix(".tmp")
    tmp.write_text(existing + json.dumps(data) + "\n", encoding="utf-8")
    tmp.replace(log_path)
    return data


def list_candidates(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent policy candidates."""
    log_path = _log_path()
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records[-limit:]


def generate_policy_candidates() -> list[dict[str, Any]]:
    """Read current patterns and generate PENDING policy candidates.

    Only generates one candidate per pattern_type (deduplicates by pattern_type).
    Returns list of newly appended candidates.
    """
    patterns = get_patterns()
    if not patterns:
        return []

    # Determine which pattern_types already have a candidate
    existing = list_candidates(limit=200)
    existing_pattern_ids = {c.get("pattern_id") for c in existing}

    new_candidates = []
    for p in patterns:
        pid = p.get("pattern_id", "")
        ptype = p.get("pattern_type", "unknown")
        if pid in existing_pattern_ids:
            continue
        suggested, risk = _PATTERN_TO_POLICY.get(ptype, (f"review pattern: {ptype}", "medium"))
        candidate = PolicyCandidate(
            candidate_id=f"pc_{uuid.uuid4().hex[:8]}",
            pattern_id=pid,
            suggested_policy=suggested,
            safety_risk=risk,
            approval_state="PENDING",
        )
        appended = append_candidate(candidate)
        new_candidates.append(appended)

    return new_candidates
