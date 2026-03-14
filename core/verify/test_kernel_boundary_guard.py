from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.runtime.kernel_boundary_guard import scan_for_kernel_boundary_violations  # noqa: E402


def test_kernel_boundary_guard_reports_no_violations() -> None:
    violations = scan_for_kernel_boundary_violations(REPO_ROOT)
    assert not violations, "kernel boundary violation(s) found:\n" + "\n".join(violations)

