"""Kernel boundary invariant scanner for runtime-reachable modules."""

from __future__ import annotations

import re
from pathlib import Path

SCAN_ROOTS = ("runtime", "interface", "core", "repos")
EXCLUDED_DIR_NAMES = {"tests", "node_modules", ".venv", "venv", "__pycache__"}

# Known legacy boundary owners allowed in this enforcement phase.
ALLOWLIST_FILES = {
    "core/activity_feed_guard.py",
    "core/config.py",
    "core/runtime/runtime_state_resolver.py",
}

RUNTIME_STATE_BYPASS_PATTERNS = [
    re.compile(r"\bruntime_root\s*/\s*[\"']state[\"']"),
    re.compile(r"\bRUNTIME_ROOT\s*/\s*[\"']state[\"']"),
    re.compile(
        r"[\"']state/(?:qs_runs|current_system\.json|approval_log\.jsonl|alerts\.jsonl|remediation_history\.jsonl)[\"']"
    ),
]

POLICY_BYPASS_PATTERNS = [
    re.compile(r"[\"']policy_memory\.json[\"']"),
    re.compile(r"[\"']approval_state\.json[\"']"),
]

EXECUTION_BRIDGE_BYPASS_PATTERN = re.compile(r"^\s*(?:from|import)\s+tools\.bridge\b")
EXECUTION_BRIDGE_ALLOWLIST_PREFIXES = ("core/task_dispatcher.py", "tools/bridge/")


def _should_skip_file(repo_root: Path, file_path: Path) -> bool:
    relative_parts = file_path.relative_to(repo_root).parts
    if any(part in EXCLUDED_DIR_NAMES for part in relative_parts):
        return True
    # Verification suites are excluded from runtime boundary enforcement.
    return len(relative_parts) >= 2 and relative_parts[0] == "core" and relative_parts[1] == "verify"


def scan_for_kernel_boundary_violations(repo_root: Path) -> list[str]:
    violations: list[str] = []
    root = repo_root.resolve()
    for root_name in SCAN_ROOTS:
        scan_root = root / root_name
        if not scan_root.exists():
            continue
        for file_path in scan_root.rglob("*.py"):
            if _should_skip_file(root, file_path):
                continue

            relative = file_path.relative_to(root).as_posix()
            if relative in ALLOWLIST_FILES:
                continue

            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line_number, line in enumerate(lines, start=1):
                if any(pattern.search(line) for pattern in RUNTIME_STATE_BYPASS_PATTERNS):
                    violations.append(
                        f"{relative}:{line_number}:runtime_state_bypass_direct_path"
                    )
                if any(pattern.search(line) for pattern in POLICY_BYPASS_PATTERNS):
                    violations.append(f"{relative}:{line_number}:policy_bypass_direct_path")
                if EXECUTION_BRIDGE_BYPASS_PATTERN.search(line) and not relative.startswith(
                    EXECUTION_BRIDGE_ALLOWLIST_PREFIXES
                ):
                    violations.append(
                        f"{relative}:{line_number}:execution_bridge_bypass_direct_import"
                    )
    return violations
