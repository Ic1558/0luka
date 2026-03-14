"""Repository invariant: forbid machine-specific absolute paths."""

from __future__ import annotations

import re
from pathlib import Path

MACHINE_PATH_PATTERNS = [
    re.compile(r"/Users/"),
    re.compile(r"/home/"),
    re.compile(r"/mnt/"),
    re.compile(r"/Volumes/"),
    re.compile(r"C:\\\\Users\\\\"),
]

SCAN_ROOTS = ("runtime", "interface", "core", "repos")
EXCLUDED_DIR_NAMES = {"tests", "node_modules", ".venv", "venv", "__pycache__"}
ALLOWLIST_FILES = {
    "core/cli.py",
    "core/config.py",
    "repos/qs/src/universal_qs_engine/qs_engine_adapter.py",
}


def _should_skip_file(repo_root: Path, file_path: Path) -> bool:
    relative_parts = file_path.relative_to(repo_root).parts
    if any(part in EXCLUDED_DIR_NAMES for part in relative_parts):
        return True
    # Verification suites are test-only and may contain detector fixtures.
    if len(relative_parts) >= 2 and relative_parts[0] == "core" and relative_parts[1] == "verify":
        return True
    return False


def _is_detector_context(line: str) -> bool:
    return (
        "re.compile(" in line
        or '"/Users/" in' in line
        or '"file:///Users" in' in line
        or "'/Users/' in" in line
        or "'file:///Users' in" in line
    )


def scan_repo_for_machine_paths(repo_root: Path) -> list[str]:
    """Return machine-path violations in relative_path:line_number:line_content format."""
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
                if _is_detector_context(line):
                    continue
                if any(pattern.search(line) for pattern in MACHINE_PATH_PATTERNS):
                    violations.append(f"{relative}:{line_number}:{line.strip()}")
    return violations

