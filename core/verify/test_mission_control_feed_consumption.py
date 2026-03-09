#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import tempfile
from pathlib import Path

from starlette.testclient import TestClient


ROOT_REPO = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT_REPO))


def _set_env(root: Path) -> dict[str, str | None]:
    old = {
        "ROOT": os.environ.get("ROOT"),
        "LUKA_RUNTIME_ROOT": os.environ.get("LUKA_RUNTIME_ROOT"),
        "LUKA_OBSERVABILITY_ROOT": os.environ.get("LUKA_OBSERVABILITY_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["LUKA_RUNTIME_ROOT"] = str(root / "runtime_root")
    os.environ["LUKA_OBSERVABILITY_ROOT"] = str(root / "observability")
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
        {"ts_utc": "2026-03-09T00:00:00Z", "action": "dispatch.start", "run_id": "mc_feed_001"},
        {"ts_utc": "2026-03-09T00:00:01Z", "action": "dispatch.end", "run_id": "mc_feed_001"},
        {"ts_utc": "2026-03-09T00:00:02Z", "action": "approval.granted", "run_id": "mc_feed_002"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_mission_control_activity_endpoint_reads_feed_truth_without_mutation() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            feed_path = root / "observability" / "logs" / "activity_feed.jsonl"
            _write_feed(feed_path)
            before = feed_path.read_text(encoding="utf-8")

            module = importlib.reload(importlib.import_module("interface.operator.mission_control_server"))
            client = TestClient(module.app)
            response = client.get("/api/activity")

            assert response.status_code == 200
            payload = response.json()
            assert isinstance(payload, list)
            assert len(payload) == 3
            assert payload[-1]["action"] == "approval.granted"
            assert feed_path.read_text(encoding="utf-8") == before
        finally:
            _restore_env(old)
