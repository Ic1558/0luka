"""AG-24A: Protected zone guard — blocks access to critical repo/system paths.

Protected zones (any path matching these prefixes/names is protected):
  - .git/ subtree (objects, pack, index, packed-refs, worktrees, hooks)
  - MCP config files
  - launchd plist files
  - runtime interpreter paths

assert_path_safe() returns ALLOW | BLOCK | ESCALATE.
Violations are logged to $LUKA_RUNTIME_ROOT/state/protected_zone_violations.jsonl.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protected zone definitions
# ---------------------------------------------------------------------------

# Path prefixes/patterns that are always protected.
# Matched against the normalized absolute path string.
_PROTECTED_PREFIXES: tuple[str, ...] = (
    ".git/",
    "/.git/",
    "/.git",          # catches .git itself
)

_PROTECTED_NAMES: frozenset[str] = frozenset({
    ".git",
    "packed-refs",
    "COMMIT_EDITMSG",
    "HEAD",
})

_PROTECTED_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"[/\\]\.git([/\\]|$)"),            # .git/ anywhere in path
    re.compile(r"[/\\]Library[/\\]LaunchAgents[/\\].*\.plist$"),  # launchd plists
    re.compile(r"[/\\]LaunchDaemons[/\\].*\.plist$"),
    re.compile(r"[/\\]\.mcp[/\\]"),                # MCP config dirs
    re.compile(r"mcp[_-]?config.*\.json$", re.IGNORECASE),
    re.compile(r"[/\\]\.venv[/\\]bin[/\\]python"),  # runtime interpreter
    re.compile(r"/usr/(local/)?bin/python"),
    re.compile(r"/opt/homebrew/.*bin/python"),
)

# Operations that are always blocked on protected paths regardless of context
_ALWAYS_BLOCK_OPS: frozenset[str] = frozenset({
    "write", "delete", "rm", "rmdir", "truncate",
    "chmod", "chown", "rename", "move", "patch",
    "git_commit", "git_push", "git_reset",
})

# Operations that escalate rather than hard-block (may be legitimate but need review)
_ESCALATE_OPS: frozenset[str] = frozenset({
    "read", "stat", "exists", "glob",
})

_VIOLATIONS_FILE = "protected_zone_violations.jsonl"


def _violations_path() -> Path | None:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        return None
    return Path(raw) / "state" / _VIOLATIONS_FILE


def _log_violation(path: str, operation: str, verdict: str) -> None:
    vpath = _violations_path()
    if vpath is None:
        return
    vpath.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "path": path,
        "operation": operation,
        "verdict": verdict,
    }
    try:
        with vpath.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError as exc:
        logger.warning("protected_zone violation log failed: %s", exc)


def _is_protected(path_str: str) -> bool:
    """Return True if the path matches any protected zone pattern."""
    for pattern in _PROTECTED_PATTERNS:
        if pattern.search(path_str):
            return True
    name = Path(path_str).name
    if name in _PROTECTED_NAMES:
        return True
    return False


def assert_path_safe(path: str | Path, operation: str) -> str:
    """Check whether an operation on a path is safe.

    Args:
        path:      Absolute or relative path string/Path being accessed.
        operation: The operation type (read, write, delete, etc.)

    Returns:
        "ALLOW" | "BLOCK" | "ESCALATE"

    Side effect:
        Logs BLOCK and ESCALATE verdicts to protected_zone_violations.jsonl.
    """
    path_str = str(path)
    op_lower = operation.strip().lower()

    if not _is_protected(path_str):
        return "ALLOW"

    # Protected path — determine verdict by operation severity
    if op_lower in _ALWAYS_BLOCK_OPS:
        logger.warning("PROTECTED ZONE BLOCK: %s on %s", operation, path_str)
        _log_violation(path_str, operation, "BLOCK")
        return "BLOCK"

    if op_lower in _ESCALATE_OPS:
        logger.info("PROTECTED ZONE ESCALATE: %s on %s", operation, path_str)
        _log_violation(path_str, operation, "ESCALATE")
        return "ESCALATE"

    # Unknown operation on protected path → block by default
    logger.warning("PROTECTED ZONE BLOCK (unknown op): %s on %s", operation, path_str)
    _log_violation(path_str, operation, "BLOCK")
    return "BLOCK"


def get_recent_violations(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent violation records (most recent last)."""
    vpath = _violations_path()
    if vpath is None or not vpath.exists():
        return []
    try:
        lines = vpath.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    bounded = max(1, min(int(limit), 500))
    return items[-bounded:]
