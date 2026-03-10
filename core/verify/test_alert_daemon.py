from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops import alert_daemon


def test_daemon_can_run_single_evaluation_cycle(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    seen: list[Path] = []

    def fake_run_once(*, runtime_root: Path | None = None):
        assert runtime_root is not None
        seen.append(runtime_root)
        return [
            {
                "timestamp": "2026-03-08T00:00:00Z",
                "severity": "CRITICAL",
                "component": "memory",
                "message": "memory_status=CRITICAL",
                "source": "alert_engine",
            }
        ]

    monkeypatch.setattr(alert_daemon.alert_engine, "run_once", fake_run_once)

    alerts = alert_daemon.run_cycle(runtime_root=runtime_root)

    assert len(alerts) == 1
    assert seen == [runtime_root]


def test_daemon_writes_logs(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(alert_daemon.alert_engine, "run_once", lambda *, runtime_root=None: [])
    monkeypatch.setattr(alert_daemon, "_utc_now", lambda: "2026-03-08T00:00:00Z")

    code = alert_daemon.run_daemon(runtime_root=runtime_root, interval=0.01, max_cycles=1)

    assert code == 0
    log_text = (runtime_root / "state" / "alert_daemon.log").read_text(encoding="utf-8")
    assert "[2026-03-08T00:00:00Z] alert daemon started" in log_text
    assert "[2026-03-08T00:00:00Z] evaluation cycle complete; alerts emitted: 0" in log_text
    assert "[2026-03-08T00:00:00Z] alert daemon stopped" in log_text


def test_daemon_triggers_alert_engine_execution(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    calls: list[int] = []

    def fake_run_once(*, runtime_root: Path | None = None):
        calls.append(1)
        return []

    monkeypatch.setattr(alert_daemon.alert_engine, "run_once", fake_run_once)

    code = alert_daemon.run_daemon(runtime_root=runtime_root, interval=0.01, max_cycles=2)

    assert code == 0
    assert len(calls) == 2


def test_daemon_exits_cleanly_on_interrupt(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setattr(alert_daemon.alert_engine, "run_once", lambda *, runtime_root=None: [])
    monkeypatch.setattr(alert_daemon.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
    monkeypatch.setattr(alert_daemon, "_utc_now", lambda: "2026-03-08T00:00:00Z")

    code = alert_daemon.run_daemon(runtime_root=runtime_root, interval=0.01)

    assert code == 0
    log_text = (runtime_root / "state" / "alert_daemon.log").read_text(encoding="utf-8")
    assert "[2026-03-08T00:00:00Z] alert daemon stopped" in log_text
