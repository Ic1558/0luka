"""AG-18: Operator escalation queue — append-only inbox for BLOCK/ESCALATE cases."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Union

from core.decision.models import DecisionRecord

_INBOX_NAME = "operator_inbox.jsonl"


def _state_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        raise RuntimeError("LUKA_RUNTIME_ROOT is required (fail-closed)")
    return Path(raw) / "state"


def _inbox_path() -> Path:
    return _state_root() / _INBOX_NAME


def enqueue_operator_case(
    decision: Union[DecisionRecord, dict],
    reason: str,
) -> None:
    """Append an escalation case to operator_inbox.jsonl (append-only).

    Args:
        decision: The decision that was BLOCK'd or ESCALATE'd.
        reason:   The policy verdict or a short explanation.
    """
    if isinstance(decision, DecisionRecord):
        record_dict = decision.to_dict()
    else:
        record_dict = dict(decision)

    entry = {
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reason": reason,
        **record_dict,
    }

    path = _inbox_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
    except OSError as exc:
        raise RuntimeError(f"operator_inbox_write_failed: {exc}") from exc


def list_operator_cases(limit: int = 50) -> list[dict]:
    """Return the most recent `limit` operator cases from the inbox."""
    path = _inbox_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    bounded = max(1, min(int(limit), 200))
    return items[-bounded:]
