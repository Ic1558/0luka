#!/usr/bin/env python3
"""Phase 11 Observer-Narrator (zero execution authority)."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.config import ROOT

EVENTS_PATH = ROOT / "observability" / "events.jsonl"
REASONING_PATH = ROOT / "observability" / "audit" / "reasoning.jsonl"
ACTIVITY_FEED_PATH = ROOT / "observability" / "activity_feed.jsonl"
AUDIT_SIGNALS_PATH = ROOT / "observability" / "artifacts" / "audit_signals.jsonl"

FORBIDDEN_IMPORT_MODULES = {
    "subprocess",
}
FORBIDDEN_CALL_NAMES = {
    "system",
    "popen",
    "dispatch_one",
    "submit_task",
    "CLECExecutor",
    "Router",
}
FORBIDDEN_TEXT_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
]
FORBIDDEN_OUTPUT_KEYS = {"command", "exec", "payload", "token", "password", "key"}


class Phase11Violation(RuntimeError):
    """Raised when observer-only constraints are violated."""


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path, limit: int = 200) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: List[Dict[str, Any]] = []
    for line in lines[-max(1, int(limit)) :]:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    safe_root = ROOT.resolve(strict=False)
    target = path.resolve(strict=False)
    inbox = (ROOT / "interface" / "inbox").resolve(strict=False)
    if str(target).startswith(str(inbox)):
        raise Phase11Violation("phase11_write_to_inbox_forbidden")
    if not str(target).startswith(str(safe_root)):
        raise Phase11Violation("phase11_write_outside_repo_forbidden")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _sanitize_string(text: str) -> str:
    s = str(text)
    s = re.sub(r"/Users/[A-Za-z0-9._-]+", "$HOME/<redacted>", s)
    s = re.sub(r"\bsk-[A-Za-z0-9]{16,}\b", "TOKEN_REDACTED", s)
    s = re.sub(r"\bghp_[A-Za-z0-9]{20,}\b", "TOKEN_REDACTED", s)
    s = re.sub(r"\bAKIA[0-9A-Z]{16}\b", "TOKEN_REDACTED", s)
    s = re.sub(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", "TOKEN_REDACTED", s)
    if "file:///" in s:
        s = s.replace("file:///", "PATH_REDACTED/")

    # Neutralize obviously executable command-channel text in narrative layer.
    if re.search(r"(;\s*rm\s+-rf\s+/|\bsudo\s+rm\b|\bgit\s+commit\b)", s, flags=re.IGNORECASE):
        s = "UNSAFE_INPUT_REDACTED"

    # Generic absolute path redaction (excluding URLs, already handled).
    s = re.sub(r"(?<!https:)(?<!http:)(?<!\w)/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+){1,}", "PATH_REDACTED", s)
    return s


def _sanitize_obj(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_string(value)
    if isinstance(value, list):
        return [_sanitize_obj(v) for v in value]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            out[str(k)] = _sanitize_obj(v)
        return out
    return value


def _contains_forbidden_text(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False)
    return any(p.search(text) for p in FORBIDDEN_TEXT_PATTERNS)


def _assert_safe_output(value: Any) -> None:
    if isinstance(value, dict):
        keys = {str(k).lower() for k in value.keys()}
        banned = keys.intersection(FORBIDDEN_OUTPUT_KEYS)
        if banned:
            raise Phase11Violation(f"phase11_forbidden_output_keys:{sorted(banned)}")
        for v in value.values():
            _assert_safe_output(v)
    elif isinstance(value, list):
        for v in value:
            _assert_safe_output(v)

    if _contains_forbidden_text(value):
        raise Phase11Violation("phase11_sensitive_leak_detected")


def _scope_for_event(event_type: str) -> str:
    if event_type.startswith("policy.") or event_type.startswith("human."):
        return "policy"
    if event_type.startswith("execution."):
        return "task"
    return "system"


def _status_for_event(event_type: str) -> str:
    if event_type in {"human.escalate", "human.clarify.requested", "policy.sentry.blocked", "policy.violation"}:
        return "requires-human-attention"
    if event_type in {"policy.sentry.warned", "execution.failed"}:
        return "warning"
    return "info"


def _build_signal(event: Dict[str, Any]) -> Dict[str, Any] | None:
    event_type = str(event.get("type") or "")
    justification = _sanitize_string(str(event.get("reason") or event.get("message") or event_type))

    if event_type in {"policy.violation", "policy.sentry.blocked"}:
        signal_type = "RISK_SPIKE"
        confidence = 0.95
    elif event_type in {"human.escalate", "policy.human_escalation.requested"}:
        signal_type = "AUTH_WALL"
        confidence = 0.9
    elif event_type in {"policy.reflect.updated", "policy.reflect.discarded"}:
        signal_type = "DRIFT"
        confidence = 0.75
    elif "UNSAFE_INPUT_REDACTED" in justification:
        signal_type = "RISK_SPIKE"
        confidence = 0.99
    else:
        return None

    blocked_items: List[str] = []
    for key in ("domain", "Target", "target", "requested_tool", "intent"):
        if key in event and event.get(key):
            blocked_items.append(_sanitize_string(str(event[key])))

    signal = {
        "schema_version": "audit.signal.v1",
        "signal_type": signal_type,
        "confidence": confidence,
        "justification": justification,
        "blocked_items": blocked_items,
        "requires_human": signal_type in {"AUTH_WALL", "RISK_SPIKE"},
    }
    _assert_safe_output(signal)
    return signal


def static_guard() -> None:
    """AST-based guard for forbidden imports/calls in this module."""
    source_path = Path(__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in FORBIDDEN_IMPORT_MODULES:
                    raise Phase11Violation(f"phase11_forbidden_import:{root_mod}")
        elif isinstance(node, ast.ImportFrom):
            root_mod = (node.module or "").split(".")[0]
            if root_mod in FORBIDDEN_IMPORT_MODULES:
                raise Phase11Violation(f"phase11_forbidden_import:{root_mod}")
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in FORBIDDEN_CALL_NAMES:
                raise Phase11Violation(f"phase11_forbidden_call:{name}")


def build_activity_feed_entry(event: Dict[str, Any], provenance_hash: str = "") -> Dict[str, Any]:
    etype = _sanitize_string(str(event.get("type") or "unknown"))
    narrative = _sanitize_string(
        f"Observed {etype} at {_sanitize_string(str(event.get('ts') or _utc_now()))}"
    )

    entry = {
        "schema_version": "activity.feed.v1",
        "activity_id": str(uuid.uuid4()),
        "ts": _sanitize_string(str(event.get("ts") or _utc_now())),
        "scope": _scope_for_event(etype),
        "status": _status_for_event(etype),
        "narrative": narrative,
        "task_id": _sanitize_string(str(event.get("task_id") or "")) or None,
        "evidence_hash": provenance_hash or _canonical_hash({"event": event}),
    }
    _assert_safe_output(entry)
    return entry


def generate_activity_intelligence(limit: int = 200, write_artifacts: bool = True) -> Dict[str, Any]:
    static_guard()

    events = _read_jsonl(EVENTS_PATH, limit=limit)
    reasoning = _read_jsonl(REASONING_PATH, limit=limit)

    out_feed: List[Dict[str, Any]] = []
    out_signals: List[Dict[str, Any]] = []

    for raw in events:
        event = _sanitize_obj(raw)
        if _contains_forbidden_text(event):
            raise Phase11Violation("phase11_sensitive_event_input_detected")

        feed_entry = build_activity_feed_entry(event)
        out_feed.append(feed_entry)
        signal = _build_signal(event)
        if signal:
            out_signals.append(signal)

    # Add one drift signal when reasoning exists but policy act chain is absent in recent window.
    if reasoning and not any((e.get("type") == "policy.act") for e in events):
        drift = {
            "schema_version": "audit.signal.v1",
            "signal_type": "DRIFT",
            "confidence": 0.7,
            "justification": "Reasoning entries observed without matching policy.act in recent window",
            "blocked_items": [],
            "requires_human": True,
        }
        _assert_safe_output(drift)
        out_signals.append(drift)

    if write_artifacts:
        for row in out_feed:
            _append_jsonl(ACTIVITY_FEED_PATH, row)
        for row in out_signals:
            _append_jsonl(AUDIT_SIGNALS_PATH, row)

    return {
        "events_processed": len(events),
        "reasoning_processed": len(reasoning),
        "activity_feed": out_feed,
        "audit_signals": out_signals,
        "activity_feed_path": str(ACTIVITY_FEED_PATH),
        "audit_signals_path": str(AUDIT_SIGNALS_PATH),
    }


__all__ = [
    "Phase11Violation",
    "generate_activity_intelligence",
    "build_activity_feed_entry",
    "static_guard",
]
