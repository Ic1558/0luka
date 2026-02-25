#!/usr/bin/env python3
"""Phase 6B regression tests for core config."""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_config_defaults_to_repo_root() -> None:
    old = os.environ.pop("ROOT", None)
    old_runtime = os.environ.get("LUKA_RUNTIME_ROOT")
    try:
        with tempfile.TemporaryDirectory() as td:
            os.environ["LUKA_RUNTIME_ROOT"] = str(Path(td).resolve())
            mod = importlib.import_module("core.config")
            mod = importlib.reload(mod)
            expected = Path(__file__).resolve().parents[2]
            assert mod.ROOT == expected
            assert mod.INBOX == expected / "interface" / "inbox"
            assert mod.OUTBOX_TASKS == expected / "interface" / "outbox" / "tasks"
            assert mod.DISPATCH_LOG == mod.RUNTIME_ROOT / "logs" / "dispatcher.jsonl"
            print("test_config_defaults_to_repo_root: ok")
    finally:
        if old is not None:
            os.environ["ROOT"] = old
        if old_runtime is None:
            os.environ.pop("LUKA_RUNTIME_ROOT", None)
        else:
            os.environ["LUKA_RUNTIME_ROOT"] = old_runtime


def test_config_honors_root_env() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        runtime_root = root / "runtime"
        old = os.environ.get("ROOT")
        old_runtime = os.environ.get("LUKA_RUNTIME_ROOT")
        os.environ["ROOT"] = str(root)
        os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)
        try:
            mod = importlib.import_module("core.config")
            mod = importlib.reload(mod)
            assert mod.ROOT == root
            assert mod.RUNTIME_ROOT == runtime_root
            assert mod.DISPATCH_LOG == runtime_root / "logs" / "dispatcher.jsonl"
            assert mod.SCHEMA_REGISTRY == root / "core" / "contracts" / "v1" / "0luka_schemas.json"
            print("test_config_honors_root_env: ok")
        finally:
            if old is None:
                os.environ.pop("ROOT", None)
            else:
                os.environ["ROOT"] = old
            if old_runtime is None:
                os.environ.pop("LUKA_RUNTIME_ROOT", None)
            else:
                os.environ["LUKA_RUNTIME_ROOT"] = old_runtime


def main() -> int:
    test_config_defaults_to_repo_root()
    test_config_honors_root_env()
    print("test_config: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
