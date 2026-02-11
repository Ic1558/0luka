#!/usr/bin/env python3
"""Phase 10 Linguist: NL intent analysis + ambiguity detection."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from core.run_provenance import append_event

AMBIGUOUS_PHRASES = {
    "do it",
    "handle it",
    "fix this",
    "make it better",
    "optimize",
    "asap",
    "something",
    "whatever",
    "quickly",
    "urgent",
}


def _signals_for(text: str) -> List[str]:
    signals: List[str] = []
    if re.search(r"\b(https?://|www\.)", text):
        signals.append("has_url")
    if "/" in text and re.search(r"/[A-Za-z0-9_.-]+", text):
        signals.append("has_path")
    if any(word in text for word in ("git", "grep", "file", "read", "local")):
        signals.append("local_ops")
    if any(word in text for word in ("cloudflare", "login", "signin", "dashboard", "auth")):
        signals.append("protected_or_auth_target")
    return signals


def analyze_intent(nl_command: str, *, actor: str = "linguist") -> Dict[str, Any]:
    text = (nl_command or "").strip()
    lowered = text.lower()

    signals = _signals_for(lowered)
    ambiguous_hits = [p for p in sorted(AMBIGUOUS_PHRASES) if p in lowered]

    too_short = len(lowered.split()) < 3
    no_action_verb = not re.search(r"\b(check|read|open|run|show|list|search|find|audit|verify|submit|dispatch|fetch)\b", lowered)
    ambiguous = bool(ambiguous_hits or (too_short and no_action_verb))

    confidence = 0.45 if ambiguous else 0.9
    if "has_url" in signals or "local_ops" in signals:
        confidence = min(0.98, confidence + 0.05)

    analysis = {
        "intent_text": text,
        "signals": signals,
        "ambiguity": {
            "is_ambiguous": ambiguous,
            "reasons": ambiguous_hits or (["insufficient_specificity"] if ambiguous else []),
        },
        "confidence": round(confidence, 2),
    }

    append_event(
        {
            "type": "policy.linguist.analyzed",
            "category": "policy",
            "actor": actor,
            "intent": text,
            "ambiguity": analysis["ambiguity"],
            "confidence": analysis["confidence"],
            "signals": analysis["signals"],
        }
    )

    if ambiguous:
        append_event(
            {
                "type": "human.clarify.requested",
                "category": "policy",
                "actor": actor,
                "intent": text,
                "reasons": analysis["ambiguity"]["reasons"],
                "message": "Intent is ambiguous. Please clarify objective, target, and expected output.",
            }
        )

    return analysis
