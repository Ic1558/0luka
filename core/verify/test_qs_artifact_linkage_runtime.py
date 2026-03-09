#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from pathlib import Path

import yaml

ROOT_REPO = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT_REPO))


def _set_env(root: Path) -> dict[str, str | None]:
    old = {
        "ROOT": os.environ.get("ROOT"),
        "0LUKA_ROOT": os.environ.get("0LUKA_ROOT"),
        "LUKA_RUNTIME_ROOT": os.environ.get("LUKA_RUNTIME_ROOT"),
        "OUTBOX_ROOT": os.environ.get("OUTBOX_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    os.environ["LUKA_RUNTIME_ROOT"] = str(root / "runtime_root")
    os.environ["OUTBOX_ROOT"] = str(root / "interface" / "outbox")
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _setup_dirs(root: Path) -> None:
    from core.verify._test_root import ensure_test_root

    ensure_test_root(root)
    (root / "runtime_root" / "logs").mkdir(parents=True, exist_ok=True)
    (root / "runtime_root" / "artifacts").mkdir(parents=True, exist_ok=True)
    (root / "runtime_root" / "state").mkdir(parents=True, exist_ok=True)


def _reload_modules():
    for name in [
        "core.config",
        "core.submit",
        "core.qs_runtime_state",
        "core.router",
        "core.task_dispatcher",
        "core.outbox_writer",
        "interface.operator.mission_control_server",
    ]:
        importlib.reload(importlib.import_module(name))


def _write_inbox_task(root: Path, task_id: str, *, artifact_refs: list[dict] | None = None) -> Path:
    payload = {
        "task_id": task_id,
        "author": "bridge",
        "call_sign": "[Bridge]",
        "root": "${ROOT}",
        "ts_utc": "2026-03-09T00:00:00Z",
        "created_at_utc": "2026-03-09T00:00:00Z",
        "intent": "qs.bridge_result.ingress",
        "schema_version": "clec.v1",
        "ops": [{"op_id": "ingress_noop", "type": "run", "command": "git status"}],
        "verify": [],
        "inputs": {
            "kind": "qs.runtime_result",
            "bridge_kind": "0luka.bridge_result",
            "run_id": task_id,
            "job_type": "qs.report_export",
            "project_id": "prj_art",
            "status": "completed",
            "payload": {
                "kind": "qs.runtime_result",
                "run_id": task_id,
                "job_type": "qs.report_export",
                "project_id": "prj_art",
                "status": "completed",
                "body": {
                    "envelope_payload": {
                        "artifact_refs": artifact_refs or [],
                    }
                },
            },
        },
    }
    inbox_path = root / "interface" / "inbox" / f"{task_id}.yaml"
    inbox_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return inbox_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_qs_artifact_linkage_is_truthful_and_reproducible() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            _reload_modules()
            dispatcher = importlib.import_module("core.task_dispatcher")
            mission = importlib.import_module("interface.operator.mission_control_server")

            refs = [
                {"artifact_type": "summary_report", "path": "output/qs/run_art_001/summary.json", "created_at": "2026-03-09T01:00:00Z"},
                {"artifact_type": "xlsx_export", "path": "output/qs/run_art_001/report.xlsx", "created_at": "2026-03-09T01:01:00Z"},
            ]
            dispatcher.dispatch_one(_write_inbox_task(root, "run_art_001", artifact_refs=refs))
            dispatcher.dispatch_one(_write_inbox_task(root, "run_art_empty", artifact_refs=[]))

            state_path = root / "runtime_root" / "state" / "qs_runs" / "run_art_001.json"
            empty_state_path = root / "runtime_root" / "state" / "qs_runs" / "run_art_empty.json"
            before_hashes = {
                "run_art_001": _sha256(state_path),
                "run_art_empty": _sha256(empty_state_path),
            }

            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            outbox_payload = json.loads((root / "interface" / "outbox" / "tasks" / "run_art_001.result.json").read_text(encoding="utf-8"))
            mission_payload = mission.load_qs_run("run_art_001")
            empty_mission_payload = mission.load_qs_run("run_art_empty")

            assert state_payload["artifacts"] == refs
            assert outbox_payload["outputs"]["json"]["ingress"]["artifacts"] == refs
            assert mission_payload["run"]["artifacts"] == refs
            assert empty_mission_payload["run"]["artifacts"] == []

            assert [row["artifact_type"] for row in mission_payload["run"]["artifacts"]] == ["summary_report", "xlsx_export"]

            repeat_one = mission.load_qs_run("run_art_001")
            repeat_summary = mission.load_qs_runs_summary()
            assert repeat_one["run"]["artifacts"] == refs
            assert any(item["run_id"] == "run_art_001" and item["artifacts"] == refs for item in repeat_summary["items"])

            after_hashes = {
                "run_art_001": _sha256(state_path),
                "run_art_empty": _sha256(empty_state_path),
            }
            assert before_hashes == after_hashes
        finally:
            from core.verify._test_root import restore_test_root_modules

            restore_test_root_modules()
            _restore_env(old)


def main() -> int:
    test_qs_artifact_linkage_is_truthful_and_reproducible()
    print("test_qs_artifact_linkage_runtime: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
