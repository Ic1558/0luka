#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _run(feed_path: Path, report_dir: Path, idle: int = 900, drift: int = 120) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["LUKA_ACTIVITY_FEED_JSONL"] = str(feed_path)
    env["LUKA_IDLE_DRIFT_REPORT_DIR"] = str(report_dir)
    env["LUKA_IDLE_THRESHOLD_SEC"] = str(idle)
    env["LUKA_DRIFT_THRESHOLD_SEC"] = str(drift)
    return subprocess.run(
        [sys.executable, "tools/ops/idle_drift_monitor.py", "--once", "--json"],
        cwd=str(Path(__file__).resolve().parents[2]),
        text=True,
        capture_output=True,
        env=env,
    )


def _latest_payload(report_dir: Path) -> dict:
    latest = report_dir / "idle_drift.latest.json"
    return json.loads(latest.read_text(encoding="utf-8"))


def test_healthy_exit_0() -> None:
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        feed = tmp / "activity.jsonl"
        report_dir = tmp / "reports"
        _write_jsonl(
            feed,
            [
                {"phase_id": "P", "action": "started", "ts": _iso(now - timedelta(seconds=10))},
                {"phase_id": "P", "action": "heartbeat", "ts": _iso(now - timedelta(seconds=5))},
            ],
        )
        proc = _run(feed, report_dir)
        assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["missing"] == []
        assert (report_dir / "idle_drift.latest.json").exists()


def test_idle_only_exit_2() -> None:
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        feed = tmp / "activity.jsonl"
        report_dir = tmp / "reports"
        _write_jsonl(
            feed,
            [
                {"phase_id": "P", "action": "started", "ts": _iso(now - timedelta(seconds=2000))},
                {"phase_id": "P", "action": "heartbeat", "ts": _iso(now - timedelta(seconds=10))},
            ],
        )
        proc = _run(feed, report_dir, idle=900, drift=120)
        assert proc.returncode == 2, proc.stdout + "\n" + proc.stderr
        payload = _latest_payload(report_dir)
        assert "idle.system.stale" in payload["missing"]
        assert "drift.heartbeat.stale" not in payload["missing"]


def test_drift_only_exit_2() -> None:
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        feed = tmp / "activity.jsonl"
        report_dir = tmp / "reports"
        _write_jsonl(
            feed,
            [
                {"phase_id": "P", "action": "started", "ts": _iso(now - timedelta(seconds=5))},
                {"phase_id": "P", "action": "heartbeat", "ts": _iso(now - timedelta(seconds=600))},
            ],
        )
        proc = _run(feed, report_dir, idle=900, drift=120)
        assert proc.returncode == 2, proc.stdout + "\n" + proc.stderr
        payload = _latest_payload(report_dir)
        assert "drift.heartbeat.stale" in payload["missing"]
        assert "idle.system.stale" not in payload["missing"]


def test_both_exit_2() -> None:
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        feed = tmp / "activity.jsonl"
        report_dir = tmp / "reports"
        _write_jsonl(
            feed,
            [
                {"phase_id": "P", "action": "started", "ts": _iso(now - timedelta(seconds=2000))},
                {"phase_id": "P", "action": "heartbeat", "ts": _iso(now - timedelta(seconds=600))},
            ],
        )
        proc = _run(feed, report_dir, idle=900, drift=120)
        assert proc.returncode == 2, proc.stdout + "\n" + proc.stderr
        payload = _latest_payload(report_dir)
        assert "idle.system.stale" in payload["missing"]
        assert "drift.heartbeat.stale" in payload["missing"]


def test_parse_error_exit_4() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        feed = tmp / "activity.jsonl"
        report_dir = tmp / "reports"
        feed.write_text("{not json}\n", encoding="utf-8")
        proc = _run(feed, report_dir)
        assert proc.returncode == 4, proc.stdout + "\n" + proc.stderr
        payload = _latest_payload(report_dir)
        assert "error.log_parse_failure" in payload["missing"]


def test_missing_log_exit_4() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        feed = tmp / "missing.jsonl"
        report_dir = tmp / "reports"
        proc = _run(feed, report_dir)
        assert proc.returncode == 4, proc.stdout + "\n" + proc.stderr
        payload = _latest_payload(report_dir)
        assert "error.log_missing_or_unreadable" in payload["missing"]


if __name__ == "__main__":
    test_healthy_exit_0()
    test_idle_only_exit_2()
    test_drift_only_exit_2()
    test_both_exit_2()
    test_parse_error_exit_4()
    test_missing_log_exit_4()
    print("test_idle_drift_monitor: all ok")
