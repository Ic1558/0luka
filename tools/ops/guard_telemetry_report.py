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


def build_report(path: Path, since_min: int, sample_limit: int = 10, max_items: int = 20) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    window_start = now_ms - max(0, int(since_min)) * 60_000

    reason_counter: Counter[str] = Counter()
    missing_combo_counter: Counter[str] = Counter()
    root_kind_counter: Counter[str] = Counter()
    sample_hashes: list[str] = []
    seen_hashes: set[str] = set()
    task_ids: set[str] = set()
    recent_blocked: list[dict[str, Any]] = []

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

        if len(recent_blocked) < max_items:
            recent_blocked.append(
                {
                    "ts_utc": str(row.get("ts_utc", "")),
                    "task_id": str(row.get("task_id", "")),
                    "reason_code": str(row.get("reason_code", "UNKNOWN")),
                    "missing_fields": cleaned if isinstance(missing_fields, list) else [],
                    "root_kind": str(row.get("root_kind", "unknown")),
                    "payload_sha256_8": str(row.get("payload_sha256_8", "")),
                }
            )

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
        "recent_blocked": recent_blocked,
    }


def _to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("## PHASE13E_GUARD_TELEMETRY")
    lines.append(f"- since_min: {report.get('since_min')}")
    totals = report.get("totals", {})
    lines.append(
        "- totals:"
        f" events={totals.get('events', 0)}"
        f" unique_task_ids={totals.get('unique_task_ids', 0)}"
        f" unique_payload_hashes={totals.get('unique_payload_hashes', 0)}"
    )
    lines.append("")
    lines.append("### Reason Breakdown")
    reason_rows = report.get("top_reason_code", [])
    if isinstance(reason_rows, list) and reason_rows:
        for row in reason_rows:
            lines.append(f"- {row.get('reason_code', 'UNKNOWN')}: {row.get('count', 0)}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("### Missing Fields Combos")
    missing_rows = report.get("top_missing_fields", [])
    if isinstance(missing_rows, list) and missing_rows:
        for row in missing_rows[:10]:
            lines.append(f"- {row.get('missing_fields', '(none)')}: {row.get('count', 0)}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("### Root Kind Distribution")
    root_rows = report.get("root_kind_distribution", [])
    if isinstance(root_rows, list) and root_rows:
        for row in root_rows:
            lines.append(f"- {row.get('root_kind', 'unknown')}: {row.get('count', 0)}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("### Recent Blocked (hash-only)")
    recent_rows = report.get("recent_blocked", [])
    if isinstance(recent_rows, list) and recent_rows:
        lines.append("| ts_utc | task_id | reason_code | missing_fields | root_kind | payload_sha256_8 |")
        lines.append("|---|---|---|---|---|---|")
        for row in recent_rows:
            missing = ",".join(str(x) for x in row.get("missing_fields", [])) if isinstance(row.get("missing_fields"), list) else ""
            lines.append(
                f"| {row.get('ts_utc', '')} | {row.get('task_id', '')} | {row.get('reason_code', 'UNKNOWN')} "
                f"| {missing or '(none)'} | {row.get('root_kind', 'unknown')} | {row.get('payload_sha256_8', '')} |"
            )
    else:
        lines.append("- (none)")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Phase13B guard telemetry from activity feed")
    parser.add_argument("--path", default="observability/logs/activity_feed.jsonl", help="Path to activity_feed jsonl")
    parser.add_argument("--since-min", type=int, default=60, help="Window in minutes (deprecated; use --since-minutes)")
    parser.add_argument("--since-minutes", type=int, default=None, help="Window in minutes")
    parser.add_argument("--limit-hashes", type=int, default=10, help="Max sample payload hashes")
    parser.add_argument("--max-items", type=int, default=20, help="Max rows for recent blocked table")
    parser.add_argument("--format", choices=["md", "json"], default="md", help="Output format")
    parser.add_argument("--json", action="store_true", help="Print JSON output (legacy alias for --format json)")
    args = parser.parse_args()

    since_min = args.since_minutes if args.since_minutes is not None else args.since_min
    report = build_report(Path(args.path), since_min=since_min, sample_limit=args.limit_hashes, max_items=args.max_items)

    output_json = args.json or args.format == "json"
    if output_json:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    print(_to_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
