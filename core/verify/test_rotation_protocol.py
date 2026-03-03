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


def test_rotation_seal_and_continuation() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            runtime_logs = root / "runtime_root" / "logs"
            runtime_logs.mkdir(parents=True, exist_ok=True)
            dispatcher_log = runtime_logs / "dispatcher.jsonl"
            dispatcher_log.write_text(
                '{"event":"dispatch.start","task_id":"t1"}\n{"event":"dispatch.end","task_id":"t1"}\n',
                encoding="utf-8",
            )

            import core.config as cfg
            importlib.reload(cfg)
            import core.rotation_protocol as rot_mod
            rot_mod = importlib.reload(rot_mod)

            seal = rot_mod.write_rotation_seal("dispatcher")
            assert seal["action"] == "rotation_seal"
            assert seal["log"] == "dispatcher"
            assert isinstance(seal.get("seal_hash"), str) and len(seal["seal_hash"]) == 64

            continuation = rot_mod.write_rotation_continuation("dispatcher")
            assert continuation["action"] == "rotation_continuation"
            assert continuation["prev_seal_hash"] == seal["seal_hash"]
            assert isinstance(continuation.get("continuation_hash"), str) and len(continuation["continuation_hash"]) == 64

            registry = runtime_logs / "rotation_registry.jsonl"
            rows = [json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert len(rows) == 2
            assert rows[0]["action"] == "rotation_seal"
            assert rows[1]["action"] == "rotation_continuation"
            print("test_rotation_seal_and_continuation: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_rotation_seal_and_continuation()
    print("test_rotation_protocol: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
