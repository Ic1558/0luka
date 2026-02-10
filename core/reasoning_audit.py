#!/usr/bin/env python3
"""Append-only reasoning audit logger for Phase 2.1."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from core.config import ROOT

REASONING_AUDIT_PATH = ROOT / "observability" / "audit" / "reasoning.jsonl"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def append_reasoning_entry(entry: Dict[str, Any]) -> None:
    """Append a single DJM entry. Raises on failure (fail-closed caller)."""
    payload = dict(entry)
    payload.setdefault("ts", _utc_now())
    REASONING_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REASONING_AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_reasoning_entries() -> list[Dict[str, Any]]:
    if not REASONING_AUDIT_PATH.exists():
        return []
    rows: list[Dict[str, Any]] = []
    for line in REASONING_AUDIT_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows
