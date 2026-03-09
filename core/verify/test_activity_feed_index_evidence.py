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


def _write_feed(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"ts_utc": "2026-03-09T00:00:00Z", "ts_epoch_ms": 1_700_000_000_000, "action": "dispatch.start", "run_id": "run_idx_001"},
        {"ts_utc": "2026-03-09T00:00:01Z", "ts_epoch_ms": 1_700_000_000_100, "action": "dispatch.end", "run_id": "run_idx_001"},
        {"ts_utc": "2026-03-09T00:00:02Z", "ts_epoch_ms": 1_700_000_000_200, "action": "approval.granted", "run_id": "run_idx_002"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_activity_feed_index_build_and_query_are_consistent() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            feed_path = root / "runtime_root" / "logs" / "activity_feed.jsonl"
            _write_feed(feed_path)

            indexer = importlib.reload(importlib.import_module("tools.ops.activity_feed_indexer"))
            query_mod = importlib.reload(importlib.import_module("tools.ops.activity_feed_query"))

            indexer.ROOT = root
            indexer.DEFAULT_FEED_PATH = feed_path
            indexer.ARCHIVE_DIR = root / "runtime_root" / "logs" / "archive"
            indexer.INDEX_DIR = root / "runtime_root" / "logs" / "index"
            indexer.BY_ACTION_DIR = indexer.INDEX_DIR / "by_action"
            indexer.BY_RUN_DIR = indexer.INDEX_DIR / "by_run"
            indexer.TS_RANGES_DIR = indexer.INDEX_DIR / "ts_ranges"
            indexer.INDEX_HEALTH_PATH = indexer.INDEX_DIR / "index_health.json"

            query_mod.ROOT = root
            query_mod.INDEX_DIR = indexer.INDEX_DIR
            query_mod.INDEX_HEALTH_PATH = indexer.INDEX_HEALTH_PATH

            indexer.build_index(feed_path)

            health = json.loads(indexer.INDEX_HEALTH_PATH.read_text(encoding="utf-8"))
            assert health["status"] == "healthy"
            assert health["files_indexed"] == 1

            by_action = query_mod.query(action="dispatch.start", limit=10)
            assert by_action["ok"] is True
            assert by_action["results_count"] == 1
            assert by_action["results"][0]["run_id"] == "run_idx_001"

            by_run = query_mod.query(run_id="run_idx_002", limit=10)
            assert by_run["ok"] is True
            assert by_run["results_count"] == 1
            assert by_run["results"][0]["action"] == "approval.granted"
            assert by_run["stale_skipped"] == 0
        finally:
            _restore_env(old)
