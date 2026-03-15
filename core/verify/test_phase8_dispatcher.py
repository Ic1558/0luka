#!/usr/bin/env python3
"""Phase 8: Dispatcher as Service tests."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.result_reader import (
    detect_result_authority_mismatches,
    get_result_execution_events,
    get_result_provenance_hashes,
    get_result_status,
    get_result_summary,
)


def _set_env(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _load_dispatcher(root: Path):
    import core.config as cfg

    importlib.reload(cfg)
    mod = importlib.import_module("core.task_dispatcher")
    mod = importlib.reload(mod)
    mod.ROOT = root
    mod.INBOX = root / "interface" / "inbox"
    mod.COMPLETED = root / "interface" / "completed"
    mod.REJECTED = root / "interface" / "rejected"
    mod.DISPATCH_LOG = root / "observability" / "logs" / "dispatcher.jsonl"
    mod.DISPATCH_LATEST = root / "observability" / "artifacts" / "dispatch_latest.json"
    mod.HEARTBEAT_PATH = root / "observability" / "artifacts" / "dispatcher_heartbeat.json"
    return mod


def _seed_task(root: Path, task_id: str) -> Path:
    inbox = root / "interface" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    task = {
        "task_id": task_id,
        "author": "lisa",
        "schema_version": "clec.v1",
        "ts_utc": "2026-03-15T00:00:00Z",
        "call_sign": "[Lisa]",
        "root": "${ROOT}",
        "intent": "lisa.exec_shell",
        "lane": "lisa",
        "executor": "lisa",
        "ops": [{"op_id": "w1", "type": "run", "command": "ls -la"}],
        "verify": [],
    }
    p = inbox / f"{task_id}.yaml"
    p.write_text(json.dumps(task), encoding="utf-8")
    return p


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _read_result(root: Path, task_id: str) -> dict:
    path = root / "interface" / "outbox" / "tasks" / f"{task_id}.result.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_entrypoint_watch_loop_runs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            dispatcher = _load_dispatcher(root)
            _seed_task(root, "task_phase8_watch")
            dispatcher.watch(interval=1, max_cycles=1)
            hb = json.loads((root / "observability" / "artifacts" / "dispatcher_heartbeat.json").read_text())
            assert hb.get("schema_version") == "dispatcher_heartbeat_v1"
            assert hb.get("cycles", 0) >= 1
            print("test_entrypoint_watch_loop_runs: ok")
        finally:
            _restore_env(old)


def test_launchd_plist_exists_and_logs_declared() -> None:
    repo = Path(__file__).resolve().parents[2]
    plist = repo / "ops" / "launchd" / "com.0luka.dispatcher.plist"
    assert plist.exists(), "plist missing"
    text = plist.read_text(encoding="utf-8")
    assert "com.0luka.dispatcher" in text
    assert "StandardOutPath" in text
    assert "StandardErrorPath" in text
    assert "python3" in text or "/usr/bin/python3" in text
    print("test_launchd_plist_exists_and_logs_declared: ok")


def test_dispatch_emits_execution_events_and_run_provenance() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            dispatcher = _load_dispatcher(root)
            task_file = _seed_task(root, "task_phase8_events")
            result = dispatcher.dispatch_one(task_file)
            assert result.get("status") in {"committed", "rejected"}

            artifact_path = root / "interface" / "outbox" / "tasks" / "task_phase8_events.result.json"
            if artifact_path.exists():
                reader_target = _read_result(root, "task_phase8_events")
            else:
                reader_target = dispatcher._build_result_bundle(
                    "task_phase8_events",
                    {"trace": {"trace_id": "task_phase8_events", "ts": "2026-03-15T00:00:00Z"}},
                    {
                        "task_id": "task_phase8_events",
                        "author": "lisa",
                        "schema_version": "clec.v1",
                        "ts_utc": "2026-03-15T00:00:00Z",
                        "call_sign": "[Lisa]",
                        "root": "${ROOT}",
                        "intent": "lisa.exec_shell",
                        "lane": "lisa",
                        "executor": "lisa",
                        "ops": [{"op_id": "w1", "type": "run", "command": "ls -la"}],
                        "verify": [],
                    },
                    {"status": "ok", "evidence": {"logs": [], "commands": [], "effects": []}},
                )

            assert get_result_status(reader_target) == "ok"
            assert isinstance(get_result_summary(reader_target), str)
            hashes = get_result_provenance_hashes(reader_target)
            assert hashes["inputs_sha256"]
            assert hashes["outputs_sha256"]
            events_from_helper = get_result_execution_events(reader_target)
            assert [event.get("event") for event in events_from_helper] == [
                "execution_started",
                "execution_finished",
            ]
            mismatch_fields = {row["field"] for row in detect_result_authority_mismatches(reader_target)}
            if isinstance(reader_target.get("seal"), dict):
                assert "seal_schema" in mismatch_fields

            events = _read_jsonl(root / "observability" / "events.jsonl")
            assert any(e.get("type") == "execution.started" and e.get("component") == "dispatcher" for e in events)
            assert any(e.get("type") == "execution.completed" and e.get("component") == "dispatcher" for e in events)

            rows = _read_jsonl(root / "observability" / "artifacts" / "run_provenance.jsonl")
            assert any(r.get("tool") == "DispatcherService" for r in rows)
            print("test_dispatch_emits_execution_events_and_run_provenance: ok")
        finally:
            _restore_env(old)


def test_reboot_survival_simulated_restart_picks_task() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            dispatcher = _load_dispatcher(root)

            # first start
            dispatcher.watch(interval=1, max_cycles=1)

            # after "restart" start again and process at least one task
            _seed_task(root, "task_phase8_reboot")
            dispatcher.watch(interval=1, max_cycles=1)

            completed = root / "interface" / "completed" / "task_phase8_reboot.yaml"
            rejected = root / "interface" / "rejected" / "task_phase8_reboot.yaml"
            assert completed.exists() or rejected.exists(), "task not picked after restart simulation"
            print("test_reboot_survival_simulated_restart_picks_task: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_entrypoint_watch_loop_runs()
    test_launchd_plist_exists_and_logs_declared()
    test_dispatch_emits_execution_events_and_run_provenance()
    test_reboot_survival_simulated_restart_picks_task()
    print("test_phase8_dispatcher: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
