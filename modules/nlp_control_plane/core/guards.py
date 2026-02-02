"""
Security Guards for NLP Control Plane
=====================================
Enforces write scope and filename safety.

COPY EXACT from tools/web_bridge/utils/rw_guard.py
"""

from pathlib import Path
import os

# CONSTANTS
PROJECT_ROOT = Path(os.environ.get("LUKA_ROOT", "/Users/icmini/0luka")).resolve()
INTERFACE_ROOT = (PROJECT_ROOT / "interface").resolve()

class SecurityViolation(Exception):
    pass

def assert_write_scope(path: Path | str) -> Path:
    """
    STRICTLY enforces that any write operation is within ~/0luka/interface/.
    Raises SecurityViolation if outside.
    Returns the resolved absolute path.
    """
    start = Path(path).resolve()

    # Check if the path is relative to INTERFACE_ROOT
    try:
        start.relative_to(INTERFACE_ROOT)
    except ValueError:
        raise SecurityViolation(f"WRITE DENIED: Path '{start}' is outside safe scope '{INTERFACE_ROOT}'")

    # Additional Guard: Explicitly block tools/ and system/ even if symlinked (though resolve() handles that)
    # This is a 'defense in depth' check.
    forbidden = [
        PROJECT_ROOT / "tools",
        PROJECT_ROOT / "system",
        PROJECT_ROOT / "core_brain"
    ]

    for bad in forbidden:
        if bad in start.parents or start == bad:
            raise SecurityViolation(f"WRITE DENIED: Path '{start}' overlaps with forbidden system directory '{bad}'")

    return start

def assert_safe_filename(filename: str) -> None:
    """
    Prevents directory traversal or weird chars in filenames.
    """
    if ".." in filename or "/" in filename or "\\" in filename:
        raise SecurityViolation(f"INVALID FILENAME: '{filename}' contains path traversal characters")

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-. ")
    if not set(filename).issubset(allowed):
        raise SecurityViolation(f"INVALID FILENAME: '{filename}' contains forbidden characters")
