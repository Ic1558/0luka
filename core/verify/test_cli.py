#!/usr/bin/env python3
"""Phase 6B regression tests for unified core CLI."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
REPO_ROOT = Path(__file__).resolve().parents[2]


def _set_env(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _setup_root(root: Path) -> None:
    from core.verify._test_root import ensure_test_root
    ensure_test_root(root)


def _load_cli():
    importlib.reload(importlib.import_module("core.config"))
    importlib.reload(importlib.import_module("core.health"))
    importlib.reload(importlib.import_module("core.ledger"))
    importlib.reload(importlib.import_module("core.submit"))
    importlib.reload(importlib.import_module("core.task_dispatcher"))
    importlib.reload(importlib.import_module("core.retention"))
    cli = importlib.import_module("core.cli")
    return importlib.reload(cli)


def test_cli_status_json() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_root(root)
            cli = _load_cli()
            buf = StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf
            try:
                rc = cli.main(["status", "--json", "--tail", "2"])
            finally:
                sys.stdout = old_stdout
            assert rc == 0
            data = json.loads(buf.getvalue())
            assert data["schema_version"] == "core_cli_status_v1"
            assert "health" in data
            print("test_cli_status_json: ok")
        finally:
            from core.verify._test_root import restore_test_root_modules
            restore_test_root_modules()
            _restore_env(old)


def test_cli_submit_from_file() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_root(root)
            cli = _load_cli()
            from core.verify._test_root import make_task
            task = root / "task.json"
            task.write_text(
                json.dumps(
                    make_task(root,
                        author="cli_test",
                        intent="cli.submit",
                        schema_version="clec.v1",
                    )
                ),
                encoding="utf-8",
            )
            rc = cli.main(["submit", "--file", str(task), "--task-id", "cli_submit_001"])
            assert rc == 0
            assert (root / "interface" / "inbox" / "cli_submit_001.yaml").exists()
            print("test_cli_submit_from_file: ok")
        finally:
            from core.verify._test_root import restore_test_root_modules
            restore_test_root_modules()
            _restore_env(old)


def main() -> int:
    test_cli_status_json()
    test_cli_submit_from_file()
    print("test_cli: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

