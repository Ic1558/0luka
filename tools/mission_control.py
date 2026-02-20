#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "observability" / "logs" / "activity_feed.jsonl"
VIOLATIONS_PATH = ROOT / "observability" / "logs" / "feed_guard_violations.jsonl"
PROOF_PACKS_PATH = ROOT / "observability" / "artifacts" / "proof_packs"


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta = {
        "path": str(path),
        "exists": path.exists(),
        "readable": True,
        "error": None,
    }
    if not path.exists():
        meta["readable"] = False
        meta["error"] = "missing"
        return [], meta

    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        meta["readable"] = False
        meta["error"] = f"read_error:{type(exc).__name__}"
        return [], meta

    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                out.append(payload)
        except json.JSONDecodeError:
            continue
    return out, meta


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_ts(row: dict[str, Any]) -> datetime | None:
    for key in ("ts", "timestamp", "ts_utc"):
        dt = _parse_ts(row.get(key))
        if dt is not None:
            return dt
    return None


def _filter_rows(rows: list[dict[str, Any]], *, tail_n: int, since_min: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_min)
    filtered: list[dict[str, Any]] = []
    parsed_count = 0
    unknown_count = 0

    for row in rows:
        dt = _extract_ts(row)
        if dt is None:
            unknown_count += 1
            continue
        parsed_count += 1
        if dt >= cutoff:
            filtered.append(row)

    tail = filtered[-tail_n:]
    summary = {
        "mode": "since_min_window",
        "since_min": since_min,
        "count_tail": len(tail),
        "count_in_window": len(filtered),
        "parsed_ts_count": parsed_count,
        "unknown_ts_count": unknown_count,
    }
    return tail, summary


def _collect_anchors() -> dict[str, Any]:
    rc_head, head, err_head = _run(["git", "rev-parse", "HEAD"])
    rc_tag, tag_sha, _ = _run(["git", "rev-list", "-n", "1", "v3_kernel_proven_clean"])
    return {
        "head_sha": head if rc_head == 0 else "unknown",
        "baseline_tag": "v3_kernel_proven_clean",
        "baseline_tag_sha": tag_sha if rc_tag == 0 else None,
        "readable": rc_head == 0,
        "error": None if rc_head == 0 else err_head,
    }


def _collect_dispatcher() -> dict[str, Any]:
    uid = str(os.getuid())
    rc, out, err = _run(["launchctl", "print", f"gui/{uid}/com.0luka.dispatcher"])
    info: dict[str, Any] = {
        "label": "com.0luka.dispatcher",
        "domain": f"gui/{uid}",
        "available": rc == 0,
        "state": None,
        "pid": None,
        "arguments": [],
        "error": err if rc != 0 else None,
    }
    if rc != 0:
        return info

    in_args = False
    for raw in out.splitlines():
        line = raw.strip()
        if line.startswith("state ="):
            info["state"] = line.split("=", 1)[1].strip()
        elif line.startswith("pid ="):
            info["pid"] = line.split("=", 1)[1].strip()
        elif line.startswith("arguments = {"):
            in_args = True
        elif in_args and line == "}":
            in_args = False
        elif in_args and line:
            info["arguments"].append(line)
    return info


def _collect_activity_feed(tail_n: int, since_min: int) -> dict[str, Any]:
    rows, meta = _read_jsonl(FEED_PATH)
    tail, base_summary = _filter_rows(rows, tail_n=tail_n, since_min=since_min)
    action_counts = Counter(str(row.get("action", "unknown")) for row in tail)
    badge_counts = Counter(str(row.get("status_badge", "unknown")) for row in tail)
    return {
        "path": str(FEED_PATH),
        "exists": meta["exists"],
        "readable": meta["readable"],
        "error": meta["error"],
        "tail": tail,
        "summary": {
            **base_summary,
            "by_action": dict(action_counts),
            "by_status_badge": dict(badge_counts),
        },
    }


def _collect_guard_violations(tail_n: int, since_min: int) -> dict[str, Any]:
    rows, meta = _read_jsonl(VIOLATIONS_PATH)
    tail, base_summary = _filter_rows(rows, tail_n=tail_n, since_min=since_min)
    reason_counts = Counter(str(row.get("reason", "unknown")) for row in tail)
    return {
        "path": str(VIOLATIONS_PATH),
        "exists": meta["exists"],
        "readable": meta["readable"],
        "error": meta["error"],
        "tail": tail,
        "summary": {
            **base_summary,
            "by_reason": dict(reason_counts),
        },
    }


def _collect_proof_packs(limit: int) -> list[dict[str, Any]]:
    if not PROOF_PACKS_PATH.exists():
        return []
    dirs = [p for p in PROOF_PACKS_PATH.iterdir() if p.is_dir()]
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for p in dirs[:limit]:
        out.append(
            {
                "name": p.name,
                "path": str(p),
                "mtime_utc": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return out


def _infer_linter_status(proof_packs: list[dict[str, Any]]) -> tuple[str, str]:
    for pack in proof_packs:
        linter_path = Path(pack["path"]) / "linter.json"
        if not linter_path.exists():
            continue
        try:
            payload = json.loads(linter_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict) and "ok" in payload:
            return ("PASS", f"from:{linter_path}") if bool(payload["ok"]) else ("FAIL", f"from:{linter_path}")
    return "UNKNOWN", "no_evidence"


def _infer_dev_health(proof_packs: list[dict[str, Any]]) -> tuple[str, str]:
    saw_pass = False
    saw_fail = False
    detail = "no_test_evidence"
    for pack in proof_packs[:10]:
        p = Path(pack["path"])
        for candidate in list(p.glob("*pytest*.txt")) + [p / "notes.txt"]:
            if not candidate.exists() or not candidate.is_file():
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace").lower()
            except Exception:
                continue
            if re.search(r"\b(failed|error|errors)\b", text):
                saw_fail = True
                detail = f"failing_tests_evidence:{candidate.name}"
            if re.search(r"\b\d+\s+passed\b", text) and "failed" not in text and "error" not in text:
                saw_pass = True
                if detail == "no_test_evidence":
                    detail = f"passing_tests_evidence:{candidate.name}"
    if saw_fail:
        return "DEGRADED", detail
    if saw_pass:
        return "HEALTHY", detail
    return "UNKNOWN", detail


def _collect_inbox(allow_inbox: bool) -> dict[str, Any]:
    if not allow_inbox:
        return {"enabled": False, "count": None}
    inbox = ROOT / "interface" / "inbox"
    if not inbox.exists() or not inbox.is_dir():
        return {"enabled": True, "count": 0}
    count = sum(1 for p in inbox.glob("*.yaml") if p.is_file())
    return {"enabled": True, "count": count}


def _build_issues(
    dispatcher: dict[str, Any],
    linter_status: str,
    feed: dict[str, Any],
    violations: dict[str, Any],
    dev_health: str,
    dev_detail: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not feed.get("readable"):
        issues.append({"code": "SOURCE_MISSING", "severity": "HIGH", "detail": f"activity_feed:{feed.get('error')}"})
    if not violations.get("readable"):
        issues.append({"code": "SOURCE_MISSING", "severity": "HIGH", "detail": f"guard_violations:{violations.get('error')}"})
    if dispatcher.get("state") != "running":
        issues.append({"code": "DISPATCHER_DOWN", "severity": "HIGH", "detail": str(dispatcher.get("error") or "state_not_running")})
    if linter_status == "FAIL":
        issues.append({"code": "LINTER_FAIL", "severity": "HIGH", "detail": "latest_linter_evidence=FAIL"})
    if linter_status == "UNKNOWN":
        issues.append({"code": "SOURCE_MISSING", "severity": "MEDIUM", "detail": "no_linter_evidence_found"})
    if int(violations["summary"]["count_in_window"]) > 0:
        issues.append({"code": "FEED_GUARD_VIOLATIONS", "severity": "HIGH", "detail": f"window_count={violations['summary']['count_in_window']}"})
    if int(feed["summary"]["unknown_ts_count"]) > 0:
        issues.append({"code": "TS_UNPARSABLE", "severity": "LOW", "detail": f"activity_feed_unknown_ts={feed['summary']['unknown_ts_count']}"})
    if int(violations["summary"]["unknown_ts_count"]) > 0:
        issues.append({"code": "TS_UNPARSABLE", "severity": "LOW", "detail": f"violations_unknown_ts={violations['summary']['unknown_ts_count']}"})
    if dev_health != "UNKNOWN":
        issues.append({"code": "DEV_HEALTH_SIGNAL", "severity": "MEDIUM", "detail": dev_detail})
    return issues


def _classify_runtime_health(dispatcher: dict[str, Any], linter_status: str, violations: dict[str, Any]) -> str:
    required_missing = (not dispatcher.get("available")) or (not violations.get("readable"))
    if required_missing:
        return "UNKNOWN"
    violation_count_window = int(violations["summary"]["count_in_window"])
    if violation_count_window > 0:
        return "CRITICAL"
    if dispatcher.get("state") != "running" or linter_status != "PASS":
        return "DEGRADED"
    return "HEALTHY"


def _collect_system_health(
    anchors: dict[str, Any],
    dispatcher: dict[str, Any],
    violations: dict[str, Any],
    linter_status: str,
    inbox: dict[str, Any],
    runtime_health: str,
    dev_health: str,
) -> dict[str, Any]:
    violations_window = int(violations["summary"]["count_in_window"])
    inbox_field = inbox["count"] if inbox.get("enabled") else "na"
    line = f"SYSTEM_HEALTH: runtime={runtime_health}, dev={dev_health}, violations={violations_window}, inbox={inbox_field}"
    return {
        "runtime": runtime_health,
        "dev": dev_health,
        "violations": violations_window,
        "inbox": inbox_field,
        "sha": anchors.get("head_sha", "unknown"),
        "line": line,
    }


def collect_summary(tail_n: int, packs_n: int, since_min: int, allow_inbox: bool) -> dict[str, Any]:
    anchors = _collect_anchors()
    dispatcher = _collect_dispatcher()
    feed = _collect_activity_feed(tail_n, since_min)
    violations = _collect_guard_violations(tail_n, since_min)
    proof_packs = _collect_proof_packs(packs_n)
    linter_status, linter_detail = _infer_linter_status(proof_packs)
    dev_health, dev_detail = _infer_dev_health(proof_packs)
    inbox = _collect_inbox(allow_inbox)
    runtime_health = _classify_runtime_health(dispatcher, linter_status, violations)
    issues = _build_issues(dispatcher, linter_status, feed, violations, dev_health, dev_detail)
    system_health = _collect_system_health(
        anchors,
        dispatcher,
        violations,
        linter_status,
        inbox,
        runtime_health,
        dev_health,
    )

    return {
        "anchors": anchors,
        "dispatcher": dispatcher,
        "activity_feed": feed,
        "guard_violations": violations,
        "proof_packs": proof_packs,
        "inbox": inbox,
        "runtime_health": runtime_health,
        "dev_health": dev_health,
        "issues": issues,
        "meta": {
            "schema_version": "v0.2-lite",
            "generated_ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "window_minutes": since_min,
            "linter_status": linter_status,
            "linter_detail": linter_detail,
            "dev_health_detail": dev_detail,
        },
        "system_health": system_health,
    }


def print_dashboard(summary: dict[str, Any]) -> None:
    anchors = summary["anchors"]
    dispatcher = summary["dispatcher"]
    feed = summary["activity_feed"]
    viol = summary["guard_violations"]
    packs = summary["proof_packs"]
    inbox = summary["inbox"]
    system_health = summary["system_health"]

    print(system_health["line"])
    print("== Mission Control Viewer v0.2-lite (Read-Only) ==")
    print("\n[1] Anchors")
    print(f"head_sha: {anchors['head_sha']}")
    print(f"baseline_tag: {anchors['baseline_tag']}")
    print(f"baseline_tag_sha: {anchors['baseline_tag_sha']}")

    print("\n[2] Dispatcher Health")
    print(f"available: {dispatcher['available']}")
    print(f"state: {dispatcher['state']}")
    print(f"pid: {dispatcher['pid']}")
    print("arguments:")
    for arg in dispatcher.get("arguments", []):
        print(f"  - {arg}")

    print("\n[3] Runtime/Dev Health")
    print(f"runtime_health: {summary['runtime_health']}")
    print(f"dev_health: {summary['dev_health']}")
    print(f"linter_status: {summary['meta']['linter_status']}")

    print("\n[4] Activity Feed Tail")
    print(f"path: {feed['path']}")
    print(f"tail_count: {feed['summary']['count_tail']}")
    print(f"window_count: {feed['summary']['count_in_window']}")
    print(f"unknown_ts_count: {feed['summary']['unknown_ts_count']}")
    print(f"by_action: {feed['summary']['by_action']}")
    print(f"by_status_badge: {feed['summary']['by_status_badge']}")

    print("\n[5] Guard Violations Tail")
    print(f"path: {viol['path']}")
    print(f"tail_count: {viol['summary']['count_tail']}")
    print(f"window_count: {viol['summary']['count_in_window']}")
    print(f"unknown_ts_count: {viol['summary']['unknown_ts_count']}")
    print(f"by_reason: {viol['summary']['by_reason']}")

    print("\n[5.5] Inbox")
    if inbox["enabled"]:
        print(f"enabled: true, count: {inbox['count']}")
    else:
        print("enabled: false, count: na")

    print("\n[6] Latest Proof Packs")
    for row in packs:
        print(f"- {row['mtime_utc']}  {row['name']}")

    print("\n[7] Issues")
    for issue in summary["issues"]:
        print(f"- {issue['severity']} {issue['code']}: {issue['detail']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mission Control Viewer v0.2-lite (read-only)")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    parser.add_argument("--tail", type=int, default=30, help="Tail line count for logs")
    parser.add_argument("--packs", type=int, default=10, help="Number of latest proof packs to show")
    parser.add_argument("--since-min", type=int, default=60, help="Time window in minutes for log filtering")
    parser.add_argument("--allow-inbox", action="store_true", help="Allow read-only inbox queue count")
    args = parser.parse_args()

    summary = collect_summary(
        tail_n=max(args.tail, 1),
        packs_n=max(args.packs, 1),
        since_min=max(args.since_min, 1),
        allow_inbox=args.allow_inbox,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_dashboard(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
