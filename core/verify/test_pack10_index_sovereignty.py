#!/usr/bin/env python3
"""Pack 10 hardening tests for index sovereignty health checks."""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _write_feed(feed_path: Path, *, count: int, action: str, run_id: str = "pack10-run") -> None:
    feed_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    base_ms = 1_700_000_000_000
    for i in range(count):
        lines.append(
            json.dumps(
                {
                    "ts_utc": f"2026-02-25T00:00:{i:02d}Z",
                    "ts_epoch_ms": base_ms + i,
                    "action": action,
                    "run_id": run_id,
                    "idx": i,
                }
            )
        )
    feed_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def _setup_indexer(root: Path):
    import tools.ops.activity_feed_indexer as indexer

    indexer = importlib.reload(indexer)
    indexer.ROOT = root
    indexer.DEFAULT_FEED_PATH = root / "observability/logs/activity_feed.jsonl"
    indexer.ARCHIVE_DIR = root / "observability/logs/archive"
    indexer.INDEX_DIR = root / "observability/logs/index"
    indexer.BY_ACTION_DIR = indexer.INDEX_DIR / "by_action"
    indexer.BY_RUN_DIR = indexer.INDEX_DIR / "by_run"
    indexer.TS_RANGES_DIR = indexer.INDEX_DIR / "ts_ranges"
    indexer.INDEX_HEALTH_PATH = indexer.INDEX_DIR / "index_health.json"
    indexer.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    return indexer


def _setup_query(root: Path):
    import tools.ops.activity_feed_query as query_mod

    query_mod = importlib.reload(query_mod)
    query_mod.ROOT = root
    query_mod.INDEX_DIR = root / "observability/logs/index"
    query_mod.INDEX_HEALTH_PATH = query_mod.INDEX_DIR / "index_health.json"
    query_mod.INDEXER = root / "tools/ops/activity_feed_indexer.py"
    return query_mod


def _setup_sovereign(root: Path):
    import tools.ops.sovereign_loop as sovereign

    sovereign = importlib.reload(sovereign)
    sovereign.ROOT = root
    sovereign.INDEX_DIR = root / "observability/logs/index"
    sovereign.INDEX_HEALTH_PATH = sovereign.INDEX_DIR / "index_health.json"
    sovereign.FEED_PATH = root / "observability/logs/activity_feed.jsonl"
    sovereign.AUDIT_DIR = root / "observability/artifacts/sovereign_runs"
    return sovereign


def _write_sovereign_inputs(root: Path) -> Tuple[Path, Path, Path]:
    policy_path = root / "core/governance/runtime_consequence_policy.yaml"
    loop_policy_path = root / "core/governance/sovereign_loop_policy.yaml"
    query_tool = root / "tools/ops/activity_feed_query.py"

    policy_path.parent.mkdir(parents=True, exist_ok=True)
    loop_policy_path.parent.mkdir(parents=True, exist_ok=True)
    query_tool.parent.mkdir(parents=True, exist_ok=True)

    policy_path.write_text("rules: []\n", encoding="utf-8")
    loop_policy_path.write_text(
        "global_limits:\n  max_actions_per_hour: 20\nconsequence_rules: {}\n",
        encoding="utf-8",
    )
    query_tool.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    return policy_path, loop_policy_path, query_tool


def test_index_health_binds_to_feed_sha() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        feed_path = root / "observability/logs/activity_feed.jsonl"
        _write_feed(feed_path, count=3, action="pack10_sha_bind")

        indexer = _setup_indexer(root)
        indexer.build_index(feed_path)

        health = json.loads((root / "observability/logs/index/index_health.json").read_text(encoding="utf-8"))
        expected_sha = hashlib.sha256(feed_path.read_bytes()).hexdigest()[:16]
        assert health.get("feed_sha") == expected_sha

        with feed_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "ts_utc": "2026-02-25T00:01:00Z",
                        "ts_epoch_ms": 1_700_000_001_000,
                        "action": "pack10_sha_bind",
                        "run_id": "pack10-run",
                    }
                )
                + "\n"
            )

        new_sha = hashlib.sha256(feed_path.read_bytes()).hexdigest()[:16]
        assert new_sha != health.get("feed_sha")

        sovereign = _setup_sovereign(root)
        policy_path, loop_policy_path, query_tool = _write_sovereign_inputs(root)
        ctrl = sovereign.SovereignControl(
            confirmed=False,
            policy_path=policy_path,
            loop_policy_path=loop_policy_path,
            query_tool=query_tool,
        )
        status = ctrl.check_index_health()
        assert status == "stale"

        events = _read_jsonl(feed_path)
        risk_events = [e for e in events if e.get("action") == "system_data_integrity_risk"]
        assert risk_events, "Expected system_data_integrity_risk event"
        assert risk_events[-1].get("reason") == "feed_sha_mismatch"


def test_stale_index_triggers_auto_rebuild_in_query() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        feed_path = root / "observability/logs/activity_feed.jsonl"
        action = "pack10_rebuild_action"
        _write_feed(feed_path, count=10, action=action)

        indexer = _setup_indexer(root)
        indexer.build_index(feed_path)

        lines = feed_path.read_text(encoding="utf-8").splitlines()
        feed_path.write_text("\n".join(lines[:5]) + "\n", encoding="utf-8")

        stale_entry = {
            "ms": 1_700_000_099_999,
            "file": str(feed_path.relative_to(root)),
            "off": 10_000_000,
            "len": 512,
        }
        stale_idx_path = root / "observability/logs/index/by_action" / f"{action}.idx.jsonl"
        with stale_idx_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(stale_entry) + "\n")

        query_mod = _setup_query(root)

        def _rebuild() -> bool:
            indexer.build_index(feed_path)
            return True

        query_mod._trigger_index_rebuild = _rebuild
        result = query_mod.query(action=action, last_min=99_999, limit=200)

        assert result["ok"] is True
        assert result["auto_rebuilt"] is True
        assert result["stale_skipped"] == 0
        assert all("error" not in item for item in result["results"])


def test_sovereign_emits_integrity_risk_when_sha_mismatch() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        feed_path = root / "observability/logs/activity_feed.jsonl"
        _write_feed(feed_path, count=1, action="pack10_integrity")

        index_dir = root / "observability/logs/index"
        index_dir.mkdir(parents=True, exist_ok=True)
        health_path = index_dir / "index_health.json"
        health_path.write_text(
            json.dumps(
                {
                    "ts_utc": "2026-02-25T00:00:00Z",
                    "status": "healthy",
                    "files_indexed": 1,
                    "last_rebuild_ts": "2026-02-25T00:00:00Z",
                    "feed_sha": "0000000000000000",
                    "feed_size": feed_path.stat().st_size,
                    "max_indexed_offset": 1,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        sovereign = _setup_sovereign(root)
        policy_path, loop_policy_path, query_tool = _write_sovereign_inputs(root)
        ctrl = sovereign.SovereignControl(
            confirmed=False,
            policy_path=policy_path,
            loop_policy_path=loop_policy_path,
            query_tool=query_tool,
        )
        status = ctrl.check_index_health()
        assert status == "stale"

        events = _read_jsonl(feed_path)
        risk_events = [e for e in events if e.get("action") == "system_data_integrity_risk"]
        assert risk_events, "Expected system_data_integrity_risk event"
        assert risk_events[-1].get("reason") == "feed_sha_mismatch"


if __name__ == "__main__":
    test_index_health_binds_to_feed_sha()
    test_stale_index_triggers_auto_rebuild_in_query()
    test_sovereign_emits_integrity_risk_when_sha_mismatch()
    print("test_pack10_index_sovereignty: 3/3 passed")
