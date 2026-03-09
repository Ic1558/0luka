from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TELEMETRY_PATH = REPO_ROOT / "observability" / "telemetry" / "ram_monitor.latest.json"


def _ensure_telemetry() -> None:
    TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TELEMETRY_PATH.exists():
        TELEMETRY_PATH.write_text('{"high_swap_activity": false, "composite_critical": false, "latch_active": false}\n', encoding="utf-8")


def _run(cmd: list[str], *, force_level: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["ROOT"] = str(REPO_ROOT)
    env["SAFE_RUN_FORCE_LEVEL"] = force_level
    if extra_env:
        env.update(extra_env)
    return subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)


def test_pytest_safe_warn_requires_force_then_allows() -> None:
    _ensure_telemetry()
    blocked = _run(["bash", "tools/ops/pytest_safe.zsh", "--no-refresh"], force_level="WARN")
    assert blocked.returncode == 41, blocked.stdout + blocked.stderr
    assert "require --force" in blocked.stderr

    allowed = _run(["bash", "tools/ops/pytest_safe.zsh", "--no-refresh", "--force"], force_level="WARN")
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "safe_run: allow level=WARN" in allowed.stdout


def test_lint_safe_warn_requires_force_then_allows() -> None:
    _ensure_telemetry()
    blocked = _run(["bash", "tools/ops/lint_safe.zsh", "--no-refresh"], force_level="WARN")
    assert blocked.returncode == 41, blocked.stdout + blocked.stderr

    allowed = _run(
        ["bash", "tools/ops/lint_safe.zsh", "--no-refresh", "--force"],
        force_level="WARN",
        extra_env={"LUKA_RUNTIME_ROOT": "/Users/icmini/0luka_runtime"},
    )
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert '"ok": true' in allowed.stdout
