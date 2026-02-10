#!/usr/bin/env python3
"""Phase 10 Sentry: forbidden/drift/abuse detection."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from core.run_provenance import append_event


class SentryBlockedError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"[{self.code}] {self.message}")


SECRET_PATTERNS = [
    r"\b(api\s*key|api_key|token|password|secret)\b",
    r"\b(find|dump|extract|list)\b.*\b(api\s*keys?|passwords?|secrets?)\b",
]
RETRY_LOOP_PATTERNS = [
    r"\b(retry\s+forever|retry\s+until\s+success|infinite\s+retry|loop\s+until)\b",
]
SHELL_ESCAPE_PATTERNS = [
    r"\b(rm\s+-rf\s+/|sudo\s+rm|chmod\s+777\s+/|/etc/passwd|\.\./|file:///)\b",
]


def _match_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def evaluate_request(nl_command: str, analysis: Dict[str, Any], *, actor: str = "sentry") -> Dict[str, Any]:
    text = (nl_command or "").strip()
    lowered = text.lower()

    violations: List[Dict[str, str]] = []
    warnings: List[str] = []

    if _match_any(lowered, SECRET_PATTERNS):
        violations.append({"code": "forbidden_secret_discovery", "reason": "Sensitive data discovery is forbidden."})
    if _match_any(lowered, RETRY_LOOP_PATTERNS):
        violations.append({"code": "forbidden_retry_loop", "reason": "Unbounded retry loops are forbidden."})
    if _match_any(lowered, SHELL_ESCAPE_PATTERNS):
        violations.append({"code": "forbidden_shell_path_escape", "reason": "Shell/path escape pattern is forbidden."})

    signals = set(analysis.get("signals") or [])
    if "protected_or_auth_target" in signals:
        warnings.append("protected_or_auth_target_requires_phase2_1_escalation")

    if violations:
        append_event(
            {
                "type": "policy.sentry.blocked",
                "category": "policy",
                "actor": actor,
                "intent": text,
                "violations": violations,
            }
        )
        first = violations[0]
        raise SentryBlockedError(first["code"], first["reason"])

    if warnings:
        append_event(
            {
                "type": "policy.sentry.warned",
                "category": "policy",
                "actor": actor,
                "intent": text,
                "warnings": warnings,
            }
        )

    return {
        "allowed": True,
        "warnings": warnings,
    }
