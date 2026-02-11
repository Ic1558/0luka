#!/usr/bin/env python3
"""Phase 5A regression tests for System Health Endpoint."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _set_env(root: Path) -> dict:
    old = {
        "ROOT": os.environ.get("ROOT"),
        "0LUKA_ROOT": os.environ.get("0LUKA_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _load_health(root: Path):
    mod = importlib.import_module("core.health")
    mod = importlib.reload(mod)
    mod.ROOT = root
    mod.HEARTBEAT = root / "observability" / "artifacts" / "dispatcher_heartbeat.json"
    mod.DISPATCH_LATEST = root / "observability" / "artifacts" / "dispatch_latest.json"
    mod.INBOX = root / "interface" / "inbox"
    mod.COMPLETED = root / "interface" / "completed"
    mod.REJECTED = root / "interface" / "rejected"
    mod.OUTBOX = root / "interface" / "outbox" / "tasks"
    mod.SCHEMA_PATH = root / "core" / "contracts" / "v1" / "0luka_schemas.json"
    mod.VERIFY_DIR = root / "core" / "verify"
    return mod


def test_health_returns_valid_report() -> None:
    """Health check should return a valid report dict."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)

        (root / "interface" / "inbox").mkdir(parents=True, exist_ok=True)
        (root / "interface" / "completed").mkdir(parents=True, exist_ok=True)
        (root / "interface" / "rejected").mkdir(parents=True, exist_ok=True)
        (root / "interface" / "outbox" / "tasks").mkdir(parents=True, exist_ok=True)
        (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)

        schema_dir = root / "core" / "contracts" / "v1"
        schema_dir.mkdir(parents=True, exist_ok=True)
        (schema_dir / "0luka_schemas.json").write_text(
            json.dumps({"$defs": {"router_audit": {}, "envelope": {}}}),
            encoding="utf-8",
        )

        health = _load_health(root)
        report = health.check_health(run_tests=False)

        assert report["schema_version"] == "health_v1"
        assert report["status"] in ("healthy", "degraded")
        assert isinstance(report["queues"], dict)
        assert isinstance(report["schemas"], dict)
        assert report["schemas"]["count"] == 2
        assert report["tests"]["ran"] is False

        print("test_health_returns_valid_report: ok")
        _restore_env(old)


def test_health_reads_heartbeat() -> None:
    """Health check should read dispatcher heartbeat."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)

        (root / "interface" / "inbox").mkdir(parents=True, exist_ok=True)
        (root / "interface" / "completed").mkdir(parents=True, exist_ok=True)
        (root / "interface" / "rejected").mkdir(parents=True, exist_ok=True)
        (root / "interface" / "outbox" / "tasks").mkdir(parents=True, exist_ok=True)

        schema_dir = root / "core" / "contracts" / "v1"
        schema_dir.mkdir(parents=True, exist_ok=True)
        (schema_dir / "0luka_schemas.json").write_text('{"$defs":{}}', encoding="utf-8")

        hb_dir = root / "observability" / "artifacts"
        hb_dir.mkdir(parents=True, exist_ok=True)
        (hb_dir / "dispatcher_heartbeat.json").write_text(
            json.dumps(
                {
                    "schema_version": "dispatcher_heartbeat_v1",
                    "ts": "2026-02-08T12:00:00Z",
                    "pid": 99999,
                    "status": "stopped",
                    "cycles": 10,
                    "uptime_sec": 50,
                }
            ),
            encoding="utf-8",
        )

        health = _load_health(root)
        report = health.check_health()

        assert report["dispatcher"]["status"] == "stopped"
        assert report["dispatcher"]["pid"] == 99999

        print("test_health_reads_heartbeat: ok")
        _restore_env(old)


def test_health_counts_queues() -> None:
    """Health check should count inbox/completed/rejected/outbox."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)

        inbox = root / "interface" / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        completed = root / "interface" / "completed"
        completed.mkdir(parents=True, exist_ok=True)
        rejected = root / "interface" / "rejected"
        rejected.mkdir(parents=True, exist_ok=True)
        outbox = root / "interface" / "outbox" / "tasks"
        outbox.mkdir(parents=True, exist_ok=True)

        (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)

        schema_dir = root / "core" / "contracts" / "v1"
        schema_dir.mkdir(parents=True, exist_ok=True)
        (schema_dir / "0luka_schemas.json").write_text('{"$defs":{}}', encoding="utf-8")

        (inbox / "task_a.yaml").write_text("id: a\n", encoding="utf-8")
        (inbox / "task_b.yaml").write_text("id: b\n", encoding="utf-8")
        (completed / "task_c.yaml").write_text("id: c\n", encoding="utf-8")
        (rejected / "task_d.yaml").write_text("id: d\n", encoding="utf-8")
        (outbox / "task_e.result.json").write_text("{}", encoding="utf-8")
        (outbox / "task_f.result.json").write_text("{}", encoding="utf-8")
        (outbox / "task_g.result.json").write_text("{}", encoding="utf-8")

        health = _load_health(root)
        report = health.check_health()

        assert report["queues"]["inbox_pending"] == 2
        assert report["queues"]["completed"] == 1
        assert report["queues"]["rejected"] == 1
        assert report["queues"]["outbox_results"] == 3

        print("test_health_counts_queues: ok")
        _restore_env(old)


def main() -> int:
    test_health_returns_valid_report()
    test_health_reads_heartbeat()
    test_health_counts_queues()
    print("test_health: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
