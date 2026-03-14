from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.policy.get_active_policy import get_active_policy  # noqa: E402
from runtime.antigravity.executor.antigravity_runtime_executor import (  # noqa: E402
    AntigravityRuntimeExecutor,
    RuntimePhase,
)


def _write_policy(path: Path, *, freeze_state: bool, version: str = "1.0") -> None:
    path.write_text(
        "\n".join(
            [
                f'version: "{version}"',
                'updated_at: "2026-03-14T00:00:00+07:00"',
                "defaults:",
                "  deny_by_default: true",
                f"  freeze_state: {'true' if freeze_state else 'false'}",
                "  max_task_size_bytes: 1048576",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_get_active_policy_reads_yaml(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, freeze_state=False, version="2.0")
    policy = get_active_policy(policy_path)
    assert policy.version == "2.0"
    assert policy.freeze_state is False
    assert policy.max_task_size_bytes == 1048576
    assert policy.deny_by_default is True


def test_get_active_policy_fails_closed_on_missing_file() -> None:
    missing = Path("__missing_policy__.yaml")
    try:
        get_active_policy(missing)
    except RuntimeError as exc:
        assert str(exc) == "policy_file_missing"
    else:
        raise AssertionError("expected policy_file_missing")


def test_get_active_policy_fails_closed_on_bad_yaml(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("defaults: [", encoding="utf-8")
    try:
        get_active_policy(policy_path)
    except RuntimeError as exc:
        assert str(exc) == "policy_parse_error"
    else:
        raise AssertionError("expected policy_parse_error")


def test_executor_blocks_on_freeze_state(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, freeze_state=True)
    executor = AntigravityRuntimeExecutor(policy_path=policy_path)
    ok = executor.verify_preconditions()
    assert ok is False
    assert executor.state.phase == RuntimePhase.BLOCKED
    assert "freeze" in executor.state.blockers[0]
    assert executor.state.policy_verdict == "blocked"


def test_executor_reads_policy_version_on_clean_pass(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    _write_policy(policy_path, freeze_state=False, version="1.0")
    executor = AntigravityRuntimeExecutor(policy_path=policy_path)
    ok = executor.verify_preconditions()
    assert ok is False
    assert executor.state.policy_version == "1.0"
    assert executor.state.policy_component == "defaults.freeze_state"
    assert executor.state.policy_verdict == "pass"

