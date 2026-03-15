"""AG-24B: Process concurrency guard — detects repo-aware process conflicts.

Scans running processes for patterns that indicate dangerous overlap:
  - duplicate sovereign loops
  - multiple repo-mutating writers
  - concurrent git workers
  - bridge watchers / consumers above threshold

State file: $LUKA_RUNTIME_ROOT/state/process_guard_log.jsonl

Result is non-blocking by itself — callers decide whether to STOP or ESCALATE.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOG_NAME = "process_guard_log.jsonl"

# Process name patterns that indicate repo-aware activity
_REPO_AWARE_PATTERNS: dict[str, str] = {
    "sovereign_loop":    "sovereign_loop.py",
    "bridge_watchdog":   "bridge_watchdog",
    "bridge_consumer":   "bridge_consumer",
    "antigravity":       "antigravity",
    "atg_bridge":        "atg_bridge",
    "mcp_server":        "mcp",
    "git_worker":        "git",
    "inbox_bridge":      "inbox_bridge",
    "repo_scanner":      "repo_scan",
}

# How many of each type triggers a conflict
_CONFLICT_THRESHOLDS: dict[str, int] = {
    "sovereign_loop":    2,   # >1 sovereign loop = conflict
    "bridge_watchdog":   2,
    "git_worker":        3,   # a few git ops ok, but >3 concurrent is suspicious
    "mcp_server":        4,
    "bridge_consumer":   5,
    "antigravity":       2,
    "default":           5,
}


def _state_root() -> Path | None:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        return None
    return Path(raw) / "state"


def _get_process_list() -> list[str]:
    """Return list of running process command lines. Fail-open on error."""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.splitlines()
    except Exception as exc:
        logger.warning("process scan failed: %s", exc)
        return []


def scan_repo_aware_processes() -> dict[str, int]:
    """Return dict of {process_type: count} for known repo-aware patterns."""
    lines = _get_process_list()
    counts: dict[str, int] = {k: 0 for k in _REPO_AWARE_PATTERNS}
    for line in lines:
        line_lower = line.lower()
        for ptype, pattern in _REPO_AWARE_PATTERNS.items():
            if pattern.lower() in line_lower:
                counts[ptype] += 1
    return counts


def detect_conflict() -> bool:
    """Return True if any process type exceeds its conflict threshold."""
    counts = scan_repo_aware_processes()
    for ptype, count in counts.items():
        threshold = _CONFLICT_THRESHOLDS.get(ptype, _CONFLICT_THRESHOLDS["default"])
        if count >= threshold:
            return True
    return False


def get_conflict_summary() -> dict[str, Any]:
    """Return full conflict summary with per-type counts and conflict flag."""
    counts = scan_repo_aware_processes()
    matched = []
    conflict = False
    for ptype, count in counts.items():
        if count == 0:
            continue
        threshold = _CONFLICT_THRESHOLDS.get(ptype, _CONFLICT_THRESHOLDS["default"])
        if count >= threshold:
            conflict = True
            matched.append(ptype)

    summary: dict[str, Any] = {
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "conflict": conflict,
        "count": sum(counts.values()),
        "matched": matched,
        "counts": {k: v for k, v in counts.items() if v > 0},
    }

    # Log to state
    root = _state_root()
    if root is not None:
        root.mkdir(parents=True, exist_ok=True)
        try:
            log = root / _LOG_NAME
            with log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(summary, sort_keys=True) + "\n")
        except OSError as exc:
            logger.warning("process_guard_log write failed: %s", exc)

    return summary
