from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops import remediation_daemon


def test_once_mode_runs_one_cycle(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    seen: list[Path] = []

    def fake_run_once(*, runtime_root: Path | None = None):
        assert runtime_root is not None
        seen.append(runtime_root)
        return [
            {
                "timestamp": "2026-03-08T00:00:00Z",
                "decision": "noop",
                "target": "none",
                "reason": "no_remediation_required",
                "action_taken": False,
                "source": "remediation_engine",
            }
        ]

    monkeypatch.setattr(remediation_daemon.remediation_engine, "run_once", fake_run_once)

    decisions = remediation_daemon.run_cycle(runtime_root=runtime_root)

    assert len(decisions) == 1
    assert seen == [runtime_root]


def test_daemon_mode_logs_started_cycle_stopped(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(remediation_daemon.remediation_engine, "run_once", lambda *, runtime_root=None: [])
    monkeypatch.setattr(remediation_daemon, "_utc_now", lambda: "2026-03-08T00:00:00Z")

    code = remediation_daemon.run_daemon(runtime_root=runtime_root, interval=0.01, max_cycles=1)

    assert code == 0
    log_text = (runtime_root / "state" / "remediation_daemon.log").read_text(encoding="utf-8")
    assert "[2026-03-08T00:00:00Z] remediation daemon started" in log_text
    assert "[2026-03-08T00:00:00Z] evaluation cycle complete; decisions: none" in log_text
    assert "[2026-03-08T00:00:00Z] remediation daemon stopped" in log_text


def test_transient_remediation_failure_does_not_kill_daemon_loop(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    calls: list[int] = []

    def fake_run_once(*, runtime_root: Path | None = None):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("transient_failure")
        return []

    monkeypatch.setattr(remediation_daemon.remediation_engine, "run_once", fake_run_once)

    code = remediation_daemon.run_daemon(runtime_root=runtime_root, interval=0.01, max_cycles=2)

    assert code == 0
    assert len(calls) == 2
    log_text = (runtime_root / "state" / "remediation_daemon.log").read_text(encoding="utf-8")
    assert "evaluation cycle failed: transient_failure" in log_text
    assert "evaluation cycle complete; decisions: none" in log_text


def test_keyboard_interrupt_exits_cleanly(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(remediation_daemon.remediation_engine, "run_once", lambda *, runtime_root=None: [])
    monkeypatch.setattr(remediation_daemon.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
    monkeypatch.setattr(remediation_daemon, "_utc_now", lambda: "2026-03-08T00:00:00Z")

    code = remediation_daemon.run_daemon(runtime_root=runtime_root, interval=0.01)

    assert code == 0
    log_text = (runtime_root / "state" / "remediation_daemon.log").read_text(encoding="utf-8")
    assert "[2026-03-08T00:00:00Z] remediation daemon stopped" in log_text


def test_remediation_daemon_log_content_valid(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(
        remediation_daemon.remediation_engine,
        "run_once",
        lambda *, runtime_root=None: [
            {
                "timestamp": "2026-03-08T00:00:00Z",
                "decision": "manual_intervention_required",
                "target": "memory",
                "reason": "memory_status=CRITICAL",
                "action_taken": False,
                "source": "remediation_engine",
            }
        ],
    )
    monkeypatch.setattr(remediation_daemon, "_utc_now", lambda: "2026-03-08T00:00:00Z")

    decisions = remediation_daemon.run_cycle(runtime_root=runtime_root)

    assert decisions[0]["decision"] == "manual_intervention_required"
    log_text = (runtime_root / "state" / "remediation_daemon.log").read_text(encoding="utf-8")
    assert "evaluation cycle complete; decisions: manual_intervention_required:memory" in log_text
