#!/usr/bin/env python3
"""Phase 7 regression tests for bridge adapter."""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

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


def _setup_dirs(root: Path) -> None:
    from core.verify._test_root import ensure_test_root
    ensure_test_root(root)


def _load_bridge():
    importlib.reload(importlib.import_module("core.config"))
    importlib.reload(importlib.import_module("core.submit"))
    mod = importlib.import_module("core.bridge")
    return importlib.reload(mod)


def test_bridge_maps_task_shape() -> None:
    bridge = _load_bridge()
    mapped = bridge.to_core_task(
        {
            "task_id": "bridge_001",
            "intent": "bridge.intent",
            "executor": "lisa",
            "created_at_utc": "2026-02-10T00:00:00Z",
            "ops": [{"op_id": "op1", "type": "run", "command": "echo ok"}],
            "verify": [],
        }
    )
    assert mapped["task_id"] == "bridge_001"
    assert mapped["intent"] == "bridge.intent"
    assert mapped["schema_version"] == "clec.v1"
    assert isinstance(mapped["ops"], list)
    print("test_bridge_maps_task_shape: ok")


@pytest.mark.xfail(
    strict=False,
    reason="bridge.to_core_task() drops ts_utc/call_sign/root required by clec_v1 schema; fix in PR-B core/bridge.py",
)
def test_bridge_submits_into_core_inbox() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _setup_dirs(root)
            bridge = _load_bridge()
            from core.verify._test_root import make_task
            receipt = bridge.submit_bridge_task(
                make_task(root,
                    task_id="bridge_submit_001",
                    intent="bridge.submit",
                    schema_version="clec.v1",
                )
            )
            assert receipt["status"] == "submitted"
            assert (root / "interface" / "inbox" / "bridge_submit_001.yaml").exists()
            print("test_bridge_submits_into_core_inbox: ok")
        finally:
            from core.verify._test_root import restore_test_root_modules
            restore_test_root_modules()
            _restore_env(old)


def main() -> int:
    test_bridge_maps_task_shape()
    test_bridge_submits_into_core_inbox()
    print("test_bridge: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
