#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_guard_telemetry_report_aggregates_and_redacts(tmp_path: Path) -> None:
    feed = tmp_path / "activity_feed.jsonl"
    rows = [
        {
            "ts_epoch_ms": 4102444800000,
            "ts_utc": "2100-01-01T00:00:00Z",
            "phase_id": "PHASE13B_GUARD_TELEMETRY",
            "action": "blocked",
            "task_id": "t1",
            "reason_code": "MISSING_REQUIRED_FIELDS",
            "missing_fields": ["ts_utc", "call_sign"],
            "root_kind": "empty",
            "payload_sha256_8": "aaaabbbb",
            "root": "/tmp/secret/should_not_appear",
        },
        {
            "ts_epoch_ms": 4102444801000,
            "ts_utc": "2100-01-01T00:00:01Z",
            "phase_id": "PHASE13B_GUARD_TELEMETRY",
            "action": "blocked",
            "task_id": "t2",
            "reason_code": "ROOT_ABSOLUTE",
            "missing_fields": [],
            "root_kind": "absolute",
            "payload_sha256_8": "ccccdddd",
        },
        {
            "ts_epoch_ms": 4102444802000,
            "ts_utc": "2100-01-01T00:00:02Z",
            "phase_id": "GOAL1_ACTIVITY_FEED",
            "action": "completed",
            "task_id": "ignore",
        },
    ]
    feed.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    cp = subprocess.run(
        [
            "python3",
            "tools/ops/guard_telemetry_report.py",
            "--path",
            str(feed),
            "--since-min",
            "999999",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    out = json.loads(cp.stdout)

    assert out["ok"] is True
    assert out["totals"]["events"] == 2
    assert out["totals"]["unique_task_ids"] == 2

    reason_counts = {r["reason_code"]: r["count"] for r in out["top_reason_code"]}
    assert reason_counts["MISSING_REQUIRED_FIELDS"] == 1
    assert reason_counts["ROOT_ABSOLUTE"] == 1

    root_dist = {r["root_kind"]: r["count"] for r in out["root_kind_distribution"]}
    assert root_dist["absolute"] == 1
    assert root_dist["empty"] == 1

    assert "aaaabbbb" in out["sample_payload_hashes"]
    assert "ccccdddd" in out["sample_payload_hashes"]

    serialized = json.dumps(out, ensure_ascii=False)
    assert "/tmp/secret/should_not_appear" not in serialized


def test_guard_telemetry_report_uses_window_filter(tmp_path: Path) -> None:
    feed = tmp_path / "activity_feed.jsonl"
    rows = [
        {
            "ts_epoch_ms": 1000,
            "ts_utc": "1970-01-01T00:00:01Z",
            "phase_id": "PHASE13B_GUARD_TELEMETRY",
            "action": "blocked",
            "task_id": "old",
            "reason_code": "MALFORMED_TASK",
            "missing_fields": [],
            "root_kind": "relative",
            "payload_sha256_8": "11112222",
        }
    ]
    feed.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    cp = subprocess.run(
        [
            "python3",
            "tools/ops/guard_telemetry_report.py",
            "--path",
            str(feed),
            "--since-min",
            "1",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    out = json.loads(cp.stdout)
    assert out["totals"]["events"] == 0
