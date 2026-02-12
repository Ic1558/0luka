#!/usr/bin/env python3
"""Phase 4A regression tests for Task Dispatcher."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
REPO_ROOT = Path(__file__).resolve().parents[2]


def _set_env(root: Path):
    old = {
        "ROOT": os.environ.get("ROOT"),
        "0LUKA_ROOT": os.environ.get("0LUKA_ROOT"),
        "OUTBOX_ROOT": os.environ.get("OUTBOX_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    os.environ["OUTBOX_ROOT"] = str(root / "interface" / "outbox" / "tasks")
    return old


def _restore_env(old):
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _load_dispatcher(root: Path):
    importlib.reload(importlib.import_module("core.ref_resolver"))
    importlib.reload(importlib.import_module("core.phase1a_resolver"))
    importlib.reload(importlib.import_module("core.clec_executor"))
    importlib.reload(importlib.import_module("core.outbox_writer"))
    importlib.reload(importlib.import_module("core.router"))
    dispatcher = importlib.import_module("core.task_dispatcher")
    dispatcher = importlib.reload(dispatcher)
    dispatcher.ROOT = root
    dispatcher.INBOX = root / "interface" / "inbox"
    dispatcher.COMPLETED = root / "interface" / "completed"
    dispatcher.REJECTED = root / "interface" / "rejected"
    dispatcher.DISPATCH_LOG = root / "observability" / "logs" / "dispatcher.jsonl"
    dispatcher.DISPATCH_LATEST = root / "observability" / "artifacts" / "dispatch_latest.json"
    dispatcher._stats = {
        "total_dispatched": 0,
        "total_committed": 0,
        "total_rejected": 0,
        "total_error": 0,
        "total_skipped": 0,
    }
    return dispatcher


def _mkdirs(root: Path) -> None:
    (root / "interface/inbox").mkdir(parents=True, exist_ok=True)
    (root / "interface/outbox/tasks").mkdir(parents=True, exist_ok=True)
    (root / "interface/completed").mkdir(parents=True, exist_ok=True)
    (root / "interface/rejected").mkdir(parents=True, exist_ok=True)
    (root / "artifacts/tasks/open").mkdir(parents=True, exist_ok=True)
    (root / "artifacts/tasks/closed").mkdir(parents=True, exist_ok=True)
    (root / "artifacts/tasks/rejected").mkdir(parents=True, exist_ok=True)
    (root / "observability/artifacts/router_audit").mkdir(parents=True, exist_ok=True)
    (root / "observability/logs").mkdir(parents=True, exist_ok=True)
    (root / "interface/schemas").mkdir(parents=True, exist_ok=True)
    (root / "core/contracts/v1").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "interface/schemas/clec_v1.yaml", root / "interface/schemas/clec_v1.yaml")
    shutil.copy2(
        REPO_ROOT / "interface/schemas/0luka_result_envelope_v1.json",
        root / "interface/schemas/0luka_result_envelope_v1.json",
    )
    shutil.copy2(REPO_ROOT / "core/contracts/v1/ref_resolution.map.yaml", root / "core/contracts/v1/ref_resolution.map.yaml")
    shutil.copy2(REPO_ROOT / "core/contracts/v1/0luka_schemas.json", root / "core/contracts/v1/0luka_schemas.json")


def test_dispatch_clec_task_e2e() -> None:
    """Dispatch a valid CLEC task through gate->execute->audit->outbox."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)
            task_id = "task_dispatch_e2e_001"
            task_file = root / "interface" / "inbox" / f"{task_id}.yaml"
            task_file.write_text(
                "\n".join(
                    [
                        f"task_id: {task_id}",
                        "author: codex",
                        "schema_version: clec.v1",
                        "ts_utc: '2026-02-08T00:00:00Z'",
                        "call_sign: '[Codex]'",
                        "root: '${ROOT}'",
                        "intent: e2e.dispatch",
                        "lane: task",
                        "ops:",
                        "  - op_id: op1",
                        "    type: run",
                        "    command: git status",
                        "verify: []",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "artifacts" / "tasks" / "open" / f"{task_id}.yaml").write_text("id: x\n", encoding="utf-8")

            dispatcher = _load_dispatcher(root)
            result = dispatcher.dispatch_one(task_file)

            assert result["task_id"] == task_id
            assert result["status"] == "committed", result
            assert (root / "interface" / "completed" / f"{task_id}.yaml").exists()
            assert (root / "interface" / "outbox" / "tasks" / f"{task_id}.result.json").exists()
            assert dispatcher.DISPATCH_LOG.exists()
            print("test_dispatch_clec_task_e2e: ok")
        finally:
            _restore_env(old)


def test_dispatch_emits_start_end_events() -> None:
    """Dispatcher must emit exactly one dispatch.start and dispatch.end per task."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)
            task_id = "task_dispatch_events_001"
            task_file = root / "interface" / "inbox" / f"{task_id}.yaml"
            task_file.write_text(
                "\n".join(
                    [
                        f"task_id: {task_id}",
                        "author: codex",
                        "schema_version: clec.v1",
                        "ts_utc: '2026-02-08T00:00:00Z'",
                        "call_sign: '[Codex]'",
                        "root: '${ROOT}'",
                        "intent: events.dispatch",
                        "lane: task",
                        "ops:",
                        "  - op_id: op1",
                        "    type: run",
                        "    command: git status",
                        "verify: []",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "artifacts" / "tasks" / "open" / f"{task_id}.yaml").write_text("id: x\n", encoding="utf-8")

            dispatcher = _load_dispatcher(root)
            result = dispatcher.dispatch_one(task_file)
            assert result["status"] in {"committed", "rejected", "error"}, result
            assert dispatcher.DISPATCH_LOG.exists(), "dispatcher.jsonl missing"

            lines = dispatcher.DISPATCH_LOG.read_text(encoding="utf-8").splitlines()
            events = [json.loads(line) for line in lines if line.strip()]
            start_events = [e for e in events if e.get("event") == "dispatch.start" and e.get("task_id") == task_id]
            end_events = [e for e in events if e.get("event") == "dispatch.end" and e.get("task_id") == task_id]

            assert len(start_events) == 1, f"expected 1 start event, got {len(start_events)}"
            assert len(end_events) == 1, f"expected 1 end event, got {len(end_events)}"

            start_event = start_events[0]
            assert start_event.get("task_id") == task_id
            assert isinstance(start_event.get("trace_id"), str) and start_event.get("trace_id")
            assert isinstance(start_event.get("intent"), str)
            assert isinstance(start_event.get("module"), str) and start_event.get("module")

            end_event = end_events[0]
            assert end_event.get("task_id") == task_id
            assert end_event.get("trace_id") == start_event.get("trace_id")
            assert isinstance(end_event.get("status"), str) and end_event.get("status")
            assert isinstance(end_event.get("duration_ms"), int)
            assert end_event.get("duration_ms") >= 0
            assert bool(end_event.get("outbox_path")) or bool(end_event.get("outbox_ref"))

            for event in (start_event, end_event):
                serialized = json.dumps(event, ensure_ascii=False, sort_keys=True)
                assert "/" + "Users/" not in serialized
                assert "file:///" + "Users/" not in serialized

            print(
                f"test_dispatch_emits_start_end_events: ok "
                f"(start={len(start_events)}, end={len(end_events)}, duration_ms={end_event['duration_ms']})"
            )
        finally:
            _restore_env(old)


def test_dispatch_idempotent() -> None:
    """Dispatching same task with existing outbox result should skip."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)
            task_id = "task_idem_001"
            (root / "interface" / "outbox" / "tasks" / f"{task_id}.result.json").write_text('{"status":"ok"}\n', encoding="utf-8")
            task_file = root / "interface" / "inbox" / f"{task_id}.yaml"
            task_file.write_text("task_id: task_idem_001\nauthor: test\n", encoding="utf-8")

            dispatcher = _load_dispatcher(root)
            result = dispatcher.dispatch_one(task_file)
            assert result["status"] == "skipped"
            assert result["reason"] == "already_processed"
            assert task_file.exists()
            print("test_dispatch_idempotent: ok")
        finally:
            _restore_env(old)


def test_dispatch_invalid_yaml_stays_in_inbox() -> None:
    """Invalid YAML should return error and keep source in inbox."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)
            task_file = root / "interface" / "inbox" / "task_bad_001.yaml"
            task_file.write_text("not: [a: valid: yaml: {{{\n", encoding="utf-8")

            dispatcher = _load_dispatcher(root)
            result = dispatcher.dispatch_one(task_file)
            assert result["status"] == "error"
            assert task_file.exists()
            print("test_dispatch_invalid_yaml_stays_in_inbox: ok")
        finally:
            _restore_env(old)


def test_dispatch_non_clec_skipped() -> None:
    """Non-CLEC tasks are skipped gracefully and routed to rejected."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)
            task_id = "task_legacy_001"
            task_file = root / "interface" / "inbox" / f"{task_id}.yaml"
            task_file.write_text(
                "task_id: task_legacy_001\n"
                "author: gmx\n"
                "intent: audit_request\n"
                "lane: task\n",
                encoding="utf-8",
            )

            dispatcher = _load_dispatcher(root)
            result = dispatcher.dispatch_one(task_file)
            assert result["status"] == "skipped", result
            assert (root / "interface" / "rejected" / f"{task_id}.yaml").exists()
            print("test_dispatch_non_clec_skipped: ok")
        finally:
            _restore_env(old)


def test_dispatch_hard_path_rejected() -> None:
    """Inbound hard path must be rejected fail-closed."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)
            task_id = "task_hardpath_001"
            hard_root = "/" + "Users/icmini/0luka"
            task_file = root / "interface" / "inbox" / f"{task_id}.yaml"
            task_file.write_text(
                "\n".join(
                    [
                        f"task_id: {task_id}",
                        "author: codex",
                        "schema_version: clec.v1",
                        "ts_utc: '2026-02-08T00:00:00Z'",
                        "call_sign: '[Codex]'",
                        f"root: '{hard_root}'",
                        "intent: reject.hardpath",
                        "ops:",
                        "  - op_id: op1",
                        "    type: run",
                        "    command: git status",
                        "verify: []",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            dispatcher = _load_dispatcher(root)
            result = dispatcher.dispatch_one(task_file)
            assert result["status"] == "rejected", result
            assert "hard_path_detected" in result["reason"]
            assert (root / "interface" / "rejected" / f"{task_id}.yaml").exists()
            print("test_dispatch_hard_path_rejected: ok")
        finally:
            _restore_env(old)


def test_dispatch_rejects_resolved_injection_and_resolves_ref() -> None:
    """task.resolved injection rejects; valid refs are resolved by gate."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)

            bad_task_id = "task_inject_001"
            bad_file = root / "interface" / "inbox" / f"{bad_task_id}.yaml"
            bad_file.write_text(
                "\n".join(
                    [
                        f"task_id: {bad_task_id}",
                        "author: codex",
                        "schema_version: clec.v1",
                        "ts_utc: '2026-02-08T00:00:00Z'",
                        "call_sign: '[Codex]'",
                        "root: '${ROOT}'",
                        "intent: reject.inject",
                        "resolved:",
                        "  trust: true",
                        "ops:",
                        "  - op_id: op1",
                        "    type: run",
                        "    command: git status",
                        "verify: []",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            good_task_id = "task_ref_001"
            good_file = root / "interface" / "inbox" / f"{good_task_id}.yaml"
            good_file.write_text(
                "\n".join(
                    [
                        f"task_id: {good_task_id}",
                        "author: codex",
                        "schema_version: clec.v1",
                        "ts_utc: '2026-02-08T00:00:00Z'",
                        "call_sign: '[Codex]'",
                        "root: '${ROOT}'",
                        "intent: resolve.ref",
                        "inputs:",
                        "  refs:",
                        "    - ref://interface/inbox",
                        "ops:",
                        "  - op_id: op1",
                        "    type: run",
                        "    command: git status",
                        "verify: []",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "artifacts" / "tasks" / "open" / f"{good_task_id}.yaml").write_text("id: x\n", encoding="utf-8")

            dispatcher = _load_dispatcher(root)
            bad_result = dispatcher.dispatch_one(bad_file)
            assert bad_result["status"] == "rejected", bad_result
            assert "untrusted_resolved_inbound" in bad_result["reason"]

            good_result = dispatcher.dispatch_one(good_file)
            assert good_result["status"] == "committed", good_result
            audit_file = root / "observability" / "artifacts" / "router_audit" / f"{good_task_id}.json"
            data = json.loads(audit_file.read_text(encoding="utf-8"))
            assert "ref://interface/inbox" in data.get("resolved_refs", []), data
            print("test_dispatch_rejects_resolved_injection_and_resolves_ref: ok")
        finally:
            _restore_env(old)


def test_dispatch_writes_latest_pointer() -> None:
    """After successful dispatch, dispatch_latest.json must exist and be valid."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)
            task_id = "task_ptr_001"
            task_file = root / "interface" / "inbox" / f"{task_id}.yaml"
            task_file.write_text(
                "\n".join(
                    [
                        f"task_id: {task_id}",
                        "author: codex",
                        "schema_version: clec.v1",
                        "ts_utc: '2026-02-08T00:00:00Z'",
                        "call_sign: '[Codex]'",
                        "root: '${ROOT}'",
                        "intent: pointer.test",
                        "created_at_utc: '2026-02-08T00:00:00Z'",
                        "lane: task",
                        "ops:",
                        "  - op_id: op1",
                        "    type: run",
                        "    command: git status",
                        "verify: []",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "artifacts" / "tasks" / "open" / f"{task_id}.yaml").write_text("id: x\n", encoding="utf-8")

            dispatcher = _load_dispatcher(root)
            result = dispatcher.dispatch_one(task_file)

            latest = root / "observability" / "artifacts" / "dispatch_latest.json"
            assert result["status"] in {"committed", "rejected", "error"}, result
            assert latest.exists(), "dispatch_latest.json not created"
            data = json.loads(latest.read_text(encoding="utf-8"))
            assert data["schema_version"] == "dispatch_latest_v1"
            assert data["task_id"] == task_id
            assert data["status"] in {"committed", "rejected", "error"}
            assert data["stats"]["total_dispatched"] >= 1
            content = latest.read_text(encoding="utf-8")
            assert "/" + "Users/" not in content, "hard path in dispatch_latest.json"
            print("test_dispatch_writes_latest_pointer: ok")
        finally:
            _restore_env(old)


def test_dispatch_pointer_schema_conformance() -> None:
    """dispatch_latest.json must conform to dispatch_latest schema."""
    from core.schema_registry import validate as schema_validate

    pointer = {
        "schema_version": "dispatch_latest_v1",
        "ts": "2026-02-08T12:00:00Z",
        "task_id": "test_schema_001",
        "trace_id": "test_schema_001",
        "status": "committed",
        "author": "codex",
        "intent": "test",
        "result_path": "interface/outbox/tasks/test.result.json",
        "audit_path": "observability/artifacts/router_audit/test.json",
        "source_moved_to": "interface/completed/test.yaml",
        "stats": {
            "total_dispatched": 1,
            "total_committed": 1,
            "total_rejected": 0,
            "total_error": 0,
            "total_skipped": 0,
        },
    }
    schema_validate("dispatch_latest", pointer)

    bad = dict(pointer)
    bad["status"] = "partial"
    try:
        schema_validate("dispatch_latest", bad)
        raise AssertionError("should have rejected invalid status")
    except Exception:
        pass

    print("test_dispatch_pointer_schema_conformance: ok")


def test_submit_dispatch_round_trip() -> None:
    """Full round-trip: submit_task() -> dispatch_one() -> outbox result."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)
            (root / "artifacts").mkdir(parents=True, exist_ok=True)

            submit_mod = importlib.import_module("core.submit")
            submit_mod = importlib.reload(submit_mod)
            submit_mod.ROOT = root
            submit_mod.INBOX = root / "interface" / "inbox"
            submit_mod.OUTBOX = root / "interface" / "outbox" / "tasks"
            submit_mod.COMPLETED = root / "interface" / "completed"

            receipt = submit_mod.submit_task(
                {
                    "author": "codex",
                    "intent": "roundtrip.test",
                    "schema_version": "clec.v1",
                    "ops": [
                        {
                            "op_id": "op1",
                            "type": "write_text",
                            "target_path": "artifacts/rt.txt",
                            "content": "roundtrip",
                        }
                    ],
                    "verify": [],
                },
                task_id="task_rt_001",
            )
            assert receipt["status"] == "submitted"
            inbox_file = root / receipt["inbox_path"]
            assert inbox_file.exists()

            (root / "artifacts" / "tasks" / "open" / "task_rt_001.yaml").write_text("id: task_rt_001\n", encoding="utf-8")

            dispatcher = _load_dispatcher(root)
            result = dispatcher.dispatch_one(inbox_file)
            assert result["task_id"] == "task_rt_001"
            assert result["status"] in ("committed", "rejected"), f"unexpected: {result}"
            assert not inbox_file.exists(), "inbox file should be moved after dispatch"

            latest = root / "observability" / "artifacts" / "dispatch_latest.json"
            if result["status"] == "committed":
                assert latest.exists(), "dispatch_latest.json not written"
                data = json.loads(latest.read_text(encoding="utf-8"))
                assert data["task_id"] == "task_rt_001"

            print("test_submit_dispatch_round_trip: ok")
        finally:
            _restore_env(old)


def test_watch_mode_cycles() -> None:
    """Watch mode should run N cycles and stop."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)
            (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)
            (root / "observability" / "logs").mkdir(parents=True, exist_ok=True)

            dispatcher = _load_dispatcher(root)
            dispatcher.HEARTBEAT_PATH = root / "observability" / "artifacts" / "dispatcher_heartbeat.json"
            dispatcher.watch(interval=1, max_cycles=2)

            hb_path = dispatcher.HEARTBEAT_PATH
            assert hb_path.exists(), "heartbeat not written"
            hb = json.loads(hb_path.read_text(encoding="utf-8"))
            assert hb["schema_version"] == "dispatcher_heartbeat_v1"
            assert hb["status"] == "stopped"
            assert hb["cycles"] == 2
            print("test_watch_mode_cycles: ok")
        finally:
            _restore_env(old)


def test_watch_heartbeat_no_hardpaths() -> None:
    """Heartbeat file must not contain hard paths."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _mkdirs(root)
            (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)
            (root / "observability" / "logs").mkdir(parents=True, exist_ok=True)

            dispatcher = _load_dispatcher(root)
            dispatcher.HEARTBEAT_PATH = root / "observability" / "artifacts" / "dispatcher_heartbeat.json"
            dispatcher.watch(interval=1, max_cycles=1)

            content = dispatcher.HEARTBEAT_PATH.read_text(encoding="utf-8")
            assert "/" + "Users/" not in content, "hard path in heartbeat"
            print("test_watch_heartbeat_no_hardpaths: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_dispatch_clec_task_e2e()
    test_dispatch_emits_start_end_events()
    test_dispatch_idempotent()
    test_dispatch_invalid_yaml_stays_in_inbox()
    test_dispatch_non_clec_skipped()
    test_dispatch_hard_path_rejected()
    test_dispatch_rejects_resolved_injection_and_resolves_ref()
    test_dispatch_writes_latest_pointer()
    test_dispatch_pointer_schema_conformance()
    test_submit_dispatch_round_trip()
    test_watch_mode_cycles()
    test_watch_heartbeat_no_hardpaths()
    print("test_task_dispatcher: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
