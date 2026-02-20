from __future__ import annotations

from pathlib import Path
import subprocess
import pytest

from core.sentry import run_preflight, SentryViolation


class _CP:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_preflight_pass_minimal(tmp_path: Path):
    # arrange
    (tmp_path / ".git").mkdir()
    (tmp_path / "observability" / "logs").mkdir(parents=True)
    (tmp_path / "observability" / "logs" / "activity_feed.jsonl").write_text("{}", encoding="utf-8")

    # act
    res = run_preflight(
        root=tmp_path,
        require_activity_feed=True,
        probe_dispatcher=False,  # unit test stays deterministic
    )

    # assert
    assert res.ok is True


def test_preflight_fail_missing_root(tmp_path: Path):
    missing = tmp_path / "nope"
    with pytest.raises(SentryViolation) as e:
        run_preflight(root=missing, require_activity_feed=False, probe_dispatcher=False)
    assert "root_missing" in str(e.value)


def test_preflight_fail_git_index_lock(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "index.lock").write_text("lock", encoding="utf-8")

    with pytest.raises(SentryViolation) as e:
        run_preflight(root=tmp_path, require_activity_feed=False, probe_dispatcher=False)
    assert "git_index_lock_present" in str(e.value)


def test_probe_dispatcher_fail_when_launchctl_not_running(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "observability" / "logs").mkdir(parents=True)
    (tmp_path / "observability" / "logs" / "activity_feed.jsonl").write_text("{}", encoding="utf-8")

    def runner(cmd, capture_output=True, text=True):
        return _CP(returncode=1, stdout="", stderr="not loaded")

    with pytest.raises(SentryViolation) as e:
        run_preflight(
            root=tmp_path,
            require_activity_feed=True,
            probe_dispatcher=True,
            runner=runner,
        )
    assert "dispatcher_not_running" in str(e.value)


def test_probe_dispatcher_fail_when_state_not_running(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "observability" / "logs").mkdir(parents=True)
    (tmp_path / "observability" / "logs" / "activity_feed.jsonl").write_text("{}", encoding="utf-8")

    def runner(cmd, capture_output=True, text=True):
        return _CP(returncode=0, stdout="state = stopped", stderr="")

    with pytest.raises(SentryViolation) as e:
        run_preflight(
            root=tmp_path,
            require_activity_feed=True,
            probe_dispatcher=True,
            runner=runner,
        )
    assert "dispatcher_not_running_state" in str(e.value)
