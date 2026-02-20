#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_epoch_ms(row: dict[str, Any]) -> int | None:
    raw = row.get("ts_epoch_ms")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)

    ts_utc = row.get("ts_utc")
    if isinstance(ts_utc, str) and ts_utc.strip():
        text = ts_utc.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            return None
    return None


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def build_report(path: Path, since_min: int, sample_limit: int = 10) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    window_start = now_ms - max(0, int(since_min)) * 60_000

    reason_counter: Counter[str] = Counter()
    missing_combo_counter: Counter[str] = Counter()
    root_kind_counter: Counter[str] = Counter()
    sample_hashes: list[str] = []
    seen_hashes: set[str] = set()
    task_ids: set[str] = set()

    total_events = 0

    for row in _iter_jsonl(path):
        epoch_ms = _parse_epoch_ms(row)
        if epoch_ms is None or epoch_ms < window_start:
            continue
        if row.get("phase_id") != "PHASE13B_GUARD_TELEMETRY":
            continue
        if row.get("action") != "blocked":
            continue

        total_events += 1
        task_id = row.get("task_id")
        if isinstance(task_id, str) and task_id.strip():
            task_ids.add(task_id)

        reason = row.get("reason_code")
        reason_counter[str(reason) if reason else "UNKNOWN"] += 1

        missing_fields = row.get("missing_fields")
        if isinstance(missing_fields, list):
            cleaned = sorted(str(x) for x in missing_fields if str(x).strip())
            combo = ",".join(cleaned) if cleaned else "(none)"
        else:
            combo = "(none)"
        missing_combo_counter[combo] += 1

        root_kind = row.get("root_kind")
        root_kind_counter[str(root_kind) if root_kind else "unknown"] += 1

        payload_hash = row.get("payload_sha256_8")
        if isinstance(payload_hash, str) and payload_hash.strip() and payload_hash not in seen_hashes:
            seen_hashes.add(payload_hash)
            if len(sample_hashes) < sample_limit:
                sample_hashes.append(payload_hash)

    return {
        "ok": True,
        "source": str(path),
        "since_min": int(since_min),
        "window_start_epoch_ms": window_start,
        "totals": {
            "events": total_events,
            "unique_task_ids": len(task_ids),
            "unique_payload_hashes": len(seen_hashes),
        },
        "top_reason_code": [
            {"reason_code": key, "count": value}
            for key, value in reason_counter.most_common()
        ],
        "top_missing_fields": [
            {"missing_fields": key, "count": value}
            for key, value in missing_combo_counter.most_common()
        ],
        "root_kind_distribution": [
            {"root_kind": key, "count": value}
            for key, value in root_kind_counter.most_common()
        ],
        "sample_payload_hashes": sample_hashes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Phase13B guard telemetry from activity feed")
    parser.add_argument("--path", default="observability/logs/activity_feed.jsonl", help="Path to activity_feed jsonl")
    parser.add_argument("--since-min", type=int, default=60, help="Window in minutes")
    parser.add_argument("--limit-hashes", type=int, default=10, help="Max sample payload hashes")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    report = build_report(Path(args.path), since_min=args.since_min, sample_limit=args.limit_hashes)

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    print(f"events={report['totals']['events']} unique_task_ids={report['totals']['unique_task_ids']}")
    print("top_reason_code:")
    for row in report["top_reason_code"][:5]:
        print(f"- {row['reason_code']}: {row['count']}")
    print("root_kind_distribution:")
    for row in report["root_kind_distribution"]:
        print(f"- {row['root_kind']}: {row['count']}")
    print("sample_payload_hashes:")
    for h in report["sample_payload_hashes"]:
        print(f"- {h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
