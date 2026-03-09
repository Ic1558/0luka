#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
LANES = ("memory", "worker")
ATTEMPT_DECISIONS = {
    "memory": {"memory_recovery_started", "memory_recovery_finished", "approval_missing", "action_unavailable", "cooldown_active", "remediation_escalated", "remediation_recovered", "remediation_state_cleared"},
    "worker": {"worker_recovery_started", "worker_recovery_finished", "approval_missing", "action_unavailable", "cooldown_active", "remediation_escalated", "remediation_recovered", "remediation_state_cleared"},
}


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _remediation_log_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / "remediation_actions.jsonl"


def _read_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def _lane_for_entry(entry: dict[str, Any]) -> str | None:
    target = str(entry.get("target", "")).lower()
    decision = str(entry.get("decision", ""))
    reason = str(entry.get("reason", "")).lower()
    if target in {"memory"}:
        return "memory"
    if target in {"worker", "bridge"}:
        return "worker"
    if "memory_status" in reason or decision.startswith("memory_"):
        return "memory"
    if "bridge_" in reason or decision.startswith("worker_"):
        return "worker"
    return None


def _default_lane_summary() -> dict[str, Any]:
    return {
        "attempts": 0,
        "cooldowns": 0,
        "escalations": 0,
        "recovered": 0,
        "events": [],
    }


def build_report(entries: list[dict[str, Any]], *, lane: str | None = None, last: int | None = None) -> dict[str, Any]:
    filtered = entries[-last:] if last is not None and last >= 0 else list(entries)
    summary = {name: _default_lane_summary() for name in LANES}
    lane_events: dict[str, list[dict[str, Any]]] = {name: [] for name in LANES}

    for entry in filtered:
        entry_lane = _lane_for_entry(entry)
        if entry_lane is None:
            continue
        if lane and entry_lane != lane:
            continue
        summary_lane = summary[entry_lane]
        decision = str(entry.get("decision", ""))
        summary_lane["events"].append(decision)
        lane_events[entry_lane].append(entry)
        if decision in ATTEMPT_DECISIONS[entry_lane] and decision not in {"remediation_recovered", "remediation_state_cleared"}:
            summary_lane["attempts"] += 1
        if decision == "cooldown_active":
            summary_lane["cooldowns"] += 1
        if decision == "remediation_escalated":
            summary_lane["escalations"] += 1
        if decision == "remediation_recovered":
            summary_lane["recovered"] += 1

    report: dict[str, Any] = {}
    for lane_name in LANES:
        if lane and lane_name != lane:
            continue
        report[lane_name] = {
            "attempts": summary[lane_name]["attempts"],
            "cooldowns": summary[lane_name]["cooldowns"],
            "escalations": summary[lane_name]["escalations"],
            "recovered": summary[lane_name]["recovered"],
            "lifecycle": [str(item.get("decision", "")) for item in lane_events[lane_name]],
        }

    last_event = filtered[-1] if filtered else None
    report["last_event"] = {
        "decision": last_event.get("decision") if isinstance(last_event, dict) else None,
        "lane": _lane_for_entry(last_event) if isinstance(last_event, dict) else None,
        "timestamp": last_event.get("timestamp") if isinstance(last_event, dict) else None,
    }
    report["total_entries"] = len(filtered)
    return report


def render_summary(report: dict[str, Any]) -> str:
    lines = ["Remediation Summary", "-------------------", ""]
    for lane in LANES:
        if lane not in report:
            continue
        item = report[lane]
        lines.extend(
            [
                f"{lane} lane",
                f"  attempts: {item.get('attempts', 0)}",
                f"  cooldowns: {item.get('cooldowns', 0)}",
                f"  escalations: {item.get('escalations', 0)}",
                f"  recovered: {item.get('recovered', 0)}",
                "",
            ]
        )
    last_event = report.get("last_event", {})
    lines.extend(
        [
            "last event:",
            f"  {last_event.get('decision') or 'n/a'}",
            f"  lane: {last_event.get('lane') or 'n/a'}",
            f"  timestamp: {last_event.get('timestamp') or 'n/a'}",
        ]
    )
    return "\n".join(lines)


def render_lane(report: dict[str, Any], lane: str) -> str:
    item = report.get(lane, {})
    lifecycle = item.get("lifecycle", [])
    lines = [f"{lane} lane lifecycle", ""]
    if lifecycle:
        lines.extend(lifecycle)
    else:
        lines.append("no_events")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render remediation outcome history from the remediation log.")
    parser.add_argument("--summary", action="store_true", help="Render human summary output")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--lane", choices=LANES, help="Filter to a single lane")
    parser.add_argument("--last", type=int, help="Use only the last N log entries")
    args = parser.parse_args()

    entries = _read_entries(_remediation_log_path(_runtime_root()))
    report = build_report(entries, lane=args.lane, last=args.last)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0

    if args.lane:
        print(render_lane(report, args.lane))
        return 0

    print(render_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
