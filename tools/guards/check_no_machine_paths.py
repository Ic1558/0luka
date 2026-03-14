#!/usr/bin/env python3
"""Guard: forbid machine-specific absolute paths in repository source files."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.runtime.invariants.no_machine_paths import scan_repo_for_machine_paths  # noqa: E402


def main() -> int:
    violations = scan_repo_for_machine_paths(REPO_ROOT)
    if violations:
        print("machine-specific absolute paths detected:")
        for violation in violations:
            print(violation)
        return 1
    print("no machine-specific absolute paths detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
