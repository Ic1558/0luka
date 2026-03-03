#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _set_env(root: Path) -> dict[str, str | None]:
    old = {
        "ROOT": os.environ.get("ROOT"),
        "0LUKA_ROOT": os.environ.get("0LUKA_ROOT"),
        "LUKA_RUNTIME_ROOT": os.environ.get("LUKA_RUNTIME_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    os.environ["LUKA_RUNTIME_ROOT"] = str(root / "runtime_root")
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def test_epoch_chain_and_hash_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            runtime_logs = root / "runtime_root" / "logs"
            runtime_logs.mkdir(parents=True, exist_ok=True)
            dispatcher_log = runtime_logs / "dispatcher.jsonl"
            dispatcher_log.write_text('{"event":"dispatch.start","task_id":"t1"}\n', encoding="utf-8")

            import core.config as cfg
            importlib.reload(cfg)
            import core.epoch_marker as epoch_mod
            epoch_mod = importlib.reload(epoch_mod)

            row1 = epoch_mod.append_epoch_marker(1)
            assert row1["prev_epoch_hash"] == epoch_mod.GENESIS_PREV_EPOCH_HASH
            assert set(row1["log_heads"].keys()) == {"dispatcher"}
            assert "activity_feed" not in row1["log_heads"]
            assert row1["epoch_hash"] == epoch_mod.compute_epoch_hash(
                row1["epoch_id"],
                row1["prev_epoch_hash"],
                row1["log_heads"],
            )

            dispatcher_log.write_text(
                dispatcher_log.read_text(encoding="utf-8") + '{"event":"dispatch.end","task_id":"t1"}\n',
                encoding="utf-8",
            )
            row2 = epoch_mod.append_epoch_marker(2)
            assert row2["prev_epoch_hash"] == row1["epoch_hash"]
            assert row2["epoch_hash"] == epoch_mod.compute_epoch_hash(
                row2["epoch_id"],
                row2["prev_epoch_hash"],
                row2["log_heads"],
            )

            manifest_lines = (runtime_logs / "epoch_manifest.jsonl").read_text(encoding="utf-8").splitlines()
            assert len(manifest_lines) == 2
            parsed = [json.loads(line) for line in manifest_lines]
            assert parsed[0]["epoch_hash"] == row1["epoch_hash"]
            assert parsed[1]["epoch_hash"] == row2["epoch_hash"]
            print("test_epoch_chain_and_hash_contract: ok")
        finally:
            _restore_env(old)


def test_emit_epoch_marker_safe_fail_open() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            import core.epoch_marker as epoch_mod
            epoch_mod = importlib.reload(epoch_mod)
            row = epoch_mod.emit_epoch_marker_safe(0)
            assert row is None
            print("test_emit_epoch_marker_safe_fail_open: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_epoch_chain_and_hash_contract()
    test_emit_epoch_marker_safe_fail_open()
    print("test_epoch_marker: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
