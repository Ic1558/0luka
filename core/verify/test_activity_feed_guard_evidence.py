#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import tempfile
from pathlib import Path


ROOT_REPO = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT_REPO))


def _set_env(root: Path) -> dict[str, str | None]:
    old = {
        "ROOT": os.environ.get("ROOT"),
        "LUKA_RUNTIME_ROOT": os.environ.get("LUKA_RUNTIME_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["LUKA_RUNTIME_ROOT"] = str(root / "runtime_root")
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def test_activity_feed_guard_appends_and_blocks_rewrite() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            runtime_root = root / "runtime_root"
            (runtime_root / "logs").mkdir(parents=True, exist_ok=True)
            (runtime_root / "state").mkdir(parents=True, exist_ok=True)
            guard = importlib.reload(importlib.import_module("core.activity_feed_guard"))

            feed_path = runtime_root / "logs" / "activity_feed.jsonl"
            state_path = runtime_root / "state" / "activity_feed_state.json"
            violation_path = runtime_root / "logs" / "feed_guard_violations.jsonl"

            ok_first = guard.guarded_append_activity_feed(
                feed_path,
                {"action": "dispatch.start", "run_id": "feed_guard_001", "ts_utc": "2026-03-09T00:00:00Z"},
                state_path=state_path,
                violation_log_path=violation_path,
            )
            ok_second = guard.guarded_append_activity_feed(
                feed_path,
                {"action": "dispatch.end", "run_id": "feed_guard_001", "ts_utc": "2026-03-09T00:00:01Z"},
                state_path=state_path,
                violation_log_path=violation_path,
            )

            assert ok_first is True
            assert ok_second is True

            canonical_feed_path = guard.CANONICAL_PRODUCTION_FEED_PATH
            lines = [json.loads(line) for line in canonical_feed_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert len(lines) == 3
            assert lines[0]["action"] == "ledger_anchor"
            assert lines[1]["prev_hash"] == lines[0]["hash"]
            assert lines[2]["prev_hash"] == lines[1]["hash"]

            tampered = lines[2]
            tampered["action"] = "tampered"
            canonical_feed_path.write_text(
                "\n".join(json.dumps(line, ensure_ascii=False) for line in [lines[0], lines[1], tampered]) + "\n",
                encoding="utf-8",
            )

            blocked = guard.guarded_append_activity_feed(
                feed_path,
                {"action": "dispatch.verify", "run_id": "feed_guard_001", "ts_utc": "2026-03-09T00:00:02Z"},
                state_path=state_path,
                violation_log_path=violation_path,
            )
            assert blocked is False

            violations = [json.loads(line) for line in violation_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            assert any(entry["reason"] in {"rewrite_detected", "truncate_detected"} for entry in violations)
        finally:
            _restore_env(old)
