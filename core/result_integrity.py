"""Mirror consistency enforcement — Legacy Mirror Retirement Phase 3: Authority Freeze."""

from __future__ import annotations

from typing import Any, Dict, List


def assert_mirror_consistency(result: Dict[str, Any]) -> None:
    """Raise RuntimeError if mirror fields diverge from execution_envelope values.

    No-op when result has no execution_envelope (pre-envelope results are exempt).
    Seal schema mismatch is not checked: envelope and legacy seals use intentionally
    different algorithms (sha256 vs hmac-sha256) and are not comparable by value.
    """
    envelope = result.get("execution_envelope")
    if not isinstance(envelope, dict):
        return

    violations: List[str] = []

    env_result = envelope.get("result") or {}

    env_status = env_result.get("status")
    if env_status and isinstance(env_status, str):
        mirror_status = result.get("status")
        if isinstance(mirror_status, str) and mirror_status and mirror_status != env_status:
            violations.append(
                f"status: envelope={env_status!r} mirror={mirror_status!r}"
            )

    env_summary = env_result.get("summary")
    if env_summary and isinstance(env_summary, str):
        mirror_summary = result.get("summary")
        if isinstance(mirror_summary, str) and mirror_summary and mirror_summary != env_summary:
            violations.append(
                f"summary: envelope={env_summary!r} mirror={mirror_summary!r}"
            )

    if violations:
        raise RuntimeError(f"mirror_authority_violation: {'; '.join(violations)}")
