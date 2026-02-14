from __future__ import annotations

import re
from email.message import EmailMessage
from typing import Any, Dict, List, Tuple


RINGS = {"R0", "R1", "R2", "R3"}
FORBIDDEN_PATTERNS = [r"\brm\s+-rf\b", r"git\s+push\s+--force", r"\bDELETE\b"]


def _sender_from_header(msg: EmailMessage) -> str:
    raw = msg.get("From", "").strip().lower()
    m = re.search(r"<([^>]+@[^>]+)>", raw)
    return (m.group(1) if m else raw).strip()


def _domain(sender: str) -> str:
    return sender.split("@", 1)[1].lower() if "@" in sender else ""


def _dkim_like_pass(msg: EmailMessage) -> bool:
    auth = msg.get("Authentication-Results", "")
    dkim = msg.get("DKIM-Status", "")
    text = f"{auth} {dkim}".lower()
    return "dkim=pass" in text or "dkim-pass" in text


def validate_email(msg: EmailMessage, parsed: Dict[str, Any], allow_domains: List[str], allow_senders: List[str], expected_token: str) -> Tuple[bool, Dict[str, Any]]:
    reasons: List[str] = []
    sender = _sender_from_header(msg)
    sender_domain = _domain(sender)

    if sender not in [s.lower() for s in allow_senders] and sender_domain not in [d.lower() for d in allow_domains]:
        reasons.append("sender_not_allowlisted")

    if not _dkim_like_pass(msg):
        reasons.append("dkim_fail_or_missing")

    token = (msg.get("X-LUKA-TOKEN", "") or parsed.get("auth.token") or "").strip()
    if not token or (expected_token and token != expected_token):
        reasons.append("token_missing_or_invalid")

    ring = str(parsed.get("ring", "")).strip().upper()
    if ring not in RINGS:
        reasons.append("ring_missing_or_invalid")

    steps = parsed.get("steps") or []
    for step in steps:
        s = str(step)
        for pat in FORBIDDEN_PATTERNS:
            if re.search(pat, s):
                if not (ring in {"R0", "R1"} and "DELETE" in pat):
                    reasons.append(f"forbidden_op:{pat}")

    ok = not reasons
    verdict = {
        "ok": ok,
        "sender": sender,
        "ring": ring,
        "reasons": sorted(set(reasons)),
    }
    return ok, verdict
