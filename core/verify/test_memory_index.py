#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_REPO = Path(__file__).resolve().parents[2]
if str(ROOT_REPO) not in sys.path:
    sys.path.insert(0, str(ROOT_REPO))


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class MemoryIndexTests(unittest.TestCase):
    def test_by_outcome_index_created_after_indexer_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runtime_root = Path(td).resolve()
            os.environ["ROOT"] = str(ROOT_REPO)
            os.environ["0LUKA_ROOT"] = str(ROOT_REPO)
            os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)

            import importlib

            importlib.reload(importlib.import_module("core.config"))
            indexer = importlib.reload(importlib.import_module("tools.ops.activity_feed_indexer"))

            feed_path = runtime_root / "logs" / "activity_feed.jsonl"
            _write_jsonl(
                feed_path,
                [
                    {"ts_epoch_ms": 1, "ts_utc": "2026-03-09T00:00:01Z", "trace_id": "t1", "status": "failed"},
                    {"ts_epoch_ms": 2, "ts_utc": "2026-03-09T00:00:02Z", "trace_id": "t2", "status": "committed"},
                ],
            )
            prov_path = runtime_root / "prov.jsonl"
            _write_jsonl(
                prov_path,
                [
                    {"trace_id": "t1", "run_id": "r1", "task_id": "r1", "job_type": "qs.report_generate", "project_id": "p1"},
                ],
            )

            indexer.build_index(feed_path, provenance_path=prov_path)
            failed_idx = runtime_root / "logs" / "index" / "by_outcome" / "failed.jsonl"
            self.assertTrue(failed_idx.exists())

    def test_query_decision_history_returns_list(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runtime_root = Path(td).resolve()
            os.environ["ROOT"] = str(ROOT_REPO)
            os.environ["0LUKA_ROOT"] = str(ROOT_REPO)
            os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)

            import importlib

            importlib.reload(importlib.import_module("core.config"))
            indexer = importlib.reload(importlib.import_module("tools.ops.activity_feed_indexer"))
            query = importlib.reload(importlib.import_module("tools.ops.activity_feed_query"))

            feed_path = runtime_root / "logs" / "activity_feed.jsonl"
            _write_jsonl(
                feed_path,
                [
                    {"ts_epoch_ms": 1, "ts_utc": "2026-03-09T00:00:01Z", "trace_id": "t1", "status": "failed"},
                ],
            )
            prov_path = runtime_root / "prov.jsonl"
            _write_jsonl(prov_path, [{"trace_id": "t1", "run_id": "r1"}])

            indexer.build_index(feed_path, provenance_path=prov_path)
            records = query.query_decision_history(n=10)
            self.assertIsInstance(records, list)

    def test_query_filters_by_status_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runtime_root = Path(td).resolve()
            os.environ["ROOT"] = str(ROOT_REPO)
            os.environ["0LUKA_ROOT"] = str(ROOT_REPO)
            os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)

            import importlib

            importlib.reload(importlib.import_module("core.config"))
            indexer = importlib.reload(importlib.import_module("tools.ops.activity_feed_indexer"))
            query = importlib.reload(importlib.import_module("tools.ops.activity_feed_query"))

            feed_path = runtime_root / "logs" / "activity_feed.jsonl"
            _write_jsonl(
                feed_path,
                [
                    {"ts_epoch_ms": 1, "ts_utc": "2026-03-09T00:00:01Z", "trace_id": "t1", "status": "failed"},
                    {"ts_epoch_ms": 2, "ts_utc": "2026-03-09T00:00:02Z", "trace_id": "t2", "status": "committed"},
                ],
            )
            prov_path = runtime_root / "prov.jsonl"
            _write_jsonl(prov_path, [])

            indexer.build_index(feed_path, provenance_path=prov_path)
            records = query.query_decision_history(n=10, status="failed")
            for record in records:
                if "status" in record:
                    self.assertEqual(str(record["status"]).lower(), "failed")

    def test_decision_history_joins_provenance_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runtime_root = Path(td).resolve()
            os.environ["ROOT"] = str(ROOT_REPO)
            os.environ["0LUKA_ROOT"] = str(ROOT_REPO)
            os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)

            import importlib

            importlib.reload(importlib.import_module("core.config"))
            indexer = importlib.reload(importlib.import_module("tools.ops.activity_feed_indexer"))
            query = importlib.reload(importlib.import_module("tools.ops.activity_feed_query"))

            feed_path = runtime_root / "logs" / "activity_feed.jsonl"
            _write_jsonl(
                feed_path,
                [
                    {"ts_epoch_ms": 1, "ts_utc": "2026-03-09T00:00:01Z", "trace_id": "t1", "status": "failed"},
                ],
            )
            prov_path = runtime_root / "prov.jsonl"
            _write_jsonl(
                prov_path,
                [
                    {
                        "trace_id": "t1",
                        "run_id": "run_001",
                        "task_id": "run_001",
                        "job_type": "qs.report_generate",
                        "project_id": "prj_001",
                    }
                ],
            )

            indexer.build_index(feed_path, provenance_path=prov_path)
            records = query.query_decision_history(n=10, status="failed")
            self.assertTrue(records)
            rec = records[-1]
            self.assertEqual(rec.get("trace_id"), "t1")
            self.assertEqual(rec.get("run_id"), "run_001")
            self.assertEqual(rec.get("job_type"), "qs.report_generate")


def main() -> int:
    unittest.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

