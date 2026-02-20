#!/usr/bin/env python3
"""Phase 5B regression tests for Production Smoke Test."""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _setup_dirs(root: Path) -> None:
    import shutil

    for rel in [
        "interface/inbox",
        "interface/outbox/tasks",
        "interface/completed",
        "interface/rejected",
        "artifacts/tasks/open",
        "artifacts/tasks/closed",
        "artifacts/tasks/rejected",
        "artifacts/smoke",
        "observability/artifacts/router_audit",
        "observability/artifacts",
        "observability/logs",
        "core/contracts/v1",
        "interface/schemas",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)
    src = REPO_ROOT / "interface" / "schemas"
    dst = root / "interface" / "schemas"
    dst.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)


def _copy_required_files(root: Path) -> None:
    import shutil

    for rel in [
        "core/contracts/v1/0luka_schemas.json",
        "core/contracts/v1/ref_resolution.map.yaml",
        "core/policy.yaml",
        "interface/schemas/clec_v1.yaml",
        "interface/schemas/0luka_result_envelope_v1.json",
        "interface/schemas/0luka_schemas_v1.json",
        "interface/schemas/phase1a_routing_v1.yaml",
        "interface/schemas/phase1a_task_v1.json",
    ]:
        src = REPO_ROOT / rel
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _load_modules(root: Path):
    smoke_mod = importlib.import_module("core.smoke")
    smoke_mod = importlib.reload(smoke_mod)
    smoke_mod.ROOT = root

    submit_mod = importlib.import_module("core.submit")
    submit_mod = importlib.reload(submit_mod)
    submit_mod.ROOT = root
    submit_mod.INBOX = root / "interface" / "inbox"
    submit_mod.OUTBOX = root / "interface" / "outbox" / "tasks"
    submit_mod.COMPLETED = root / "interface" / "completed"

    dispatcher_mod = importlib.import_module("core.task_dispatcher")
    dispatcher_mod = importlib.reload(dispatcher_mod)
    dispatcher_mod.ROOT = root
    dispatcher_mod.INBOX = root / "interface" / "inbox"
    dispatcher_mod.COMPLETED = root / "interface" / "completed"
    dispatcher_mod.REJECTED = root / "interface" / "rejected"
    dispatcher_mod.DISPATCH_LOG = root / "observability" / "logs" / "dispatcher.jsonl"
    dispatcher_mod.DISPATCH_LATEST = root / "observability" / "artifacts" / "dispatch_latest.json"
    dispatcher_mod.HEARTBEAT_PATH = root / "observability" / "artifacts" / "dispatcher_heartbeat.json"

    return smoke_mod


def test_smoke_clean_passes() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        _setup_dirs(root)
        _copy_required_files(root)

        smoke = _load_modules(root)
        result = smoke.run_smoke(clean=True)

        assert result.passed, f"smoke failed: {[s for s in result.steps if not s['ok']]}"
        assert result.task_id.startswith("smoke_")

        outbox = root / "interface" / "outbox" / "tasks" / f"{result.task_id}.result.json"
        assert not outbox.exists(), "outbox should be cleaned"

        print("test_smoke_clean_passes: ok")
        _restore_env(old)


def test_smoke_result_schema() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        _setup_dirs(root)
        _copy_required_files(root)

        smoke = _load_modules(root)
        result = smoke.run_smoke(clean=True)
        data = result.to_dict()

        assert data["schema_version"] == "smoke_v1"
        assert isinstance(data["steps"], list)
        assert len(data["steps"]) > 0
        assert isinstance(data["passed"], bool)
        assert data["task_id"].startswith("smoke_")

        print("test_smoke_result_schema: ok")
        _restore_env(old)


def main() -> int:
    test_smoke_clean_passes()
    test_smoke_result_schema()
    print("test_smoke: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
