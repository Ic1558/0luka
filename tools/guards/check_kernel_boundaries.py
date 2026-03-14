#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.runtime.kernel_boundary_guard import scan_for_kernel_boundary_violations  # noqa: E402


def main() -> int:
    violations = scan_for_kernel_boundary_violations(REPO_ROOT)
    if violations:
        print("kernel boundary violation(s) detected:")
        for violation in violations:
            print(violation)
        return 1
    print("no kernel boundary violations detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

