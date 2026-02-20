#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "observability" / "logs" / "activity_feed.jsonl"
VIOLATIONS_PATH = ROOT / "observability" / "logs" / "feed_guard_violations.jsonl"
PROOF_PACKS_PATH = ROOT / "observability" / "artifacts" / "proof_packs"


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _read_tail_jsonl(path: Path, n: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-n:]:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                out.append(payload)
        except json.JSONDecodeError:
            continue
    return out


def _collect_anchors() -> dict[str, Any]:
    _, head, _ = _run(["git", "rev-parse", "HEAD"])
    rc_tag, tag_sha, _ = _run(["git", "rev-list", "-n", "1", "v3_kernel_proven_clean"])
    return {
        "head_sha": head,
        "baseline_tag": "v3_kernel_proven_clean",
        "baseline_tag_sha": tag_sha if rc_tag == 0 else None,
    }


def _collect_dispatcher() -> dict[str, Any]:
    uid = str(os.getuid())
    cmd = ["launchctl", "print", f"gui/{uid}/com.0luka.dispatcher"]
    rc, out, err = _run(cmd)
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


def _collect_activity_feed(tail_n: int) -> dict[str, Any]:
    tail = _read_tail_jsonl(FEED_PATH, tail_n)
    action_counts = Counter()
    badge_counts = Counter()
    for row in tail:
        action = str(row.get("action", "unknown"))
        badge = str(row.get("status_badge", "unknown"))
        action_counts[action] += 1
        badge_counts[badge] += 1
    return {
        "path": str(FEED_PATH),
        "exists": FEED_PATH.exists(),
        "tail": tail,
        "summary": {
            "count_tail": len(tail),
            "by_action": dict(action_counts),
            "by_status_badge": dict(badge_counts),
        },
    }


def _collect_guard_violations(tail_n: int) -> dict[str, Any]:
    tail = _read_tail_jsonl(VIOLATIONS_PATH, tail_n)
    reason_counts = Counter(str(row.get("reason", "unknown")) for row in tail)
    return {
        "path": str(VIOLATIONS_PATH),
        "exists": VIOLATIONS_PATH.exists(),
        "tail": tail,
        "summary": {
            "count_tail": len(tail),
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


def collect_summary(tail_n: int, packs_n: int) -> dict[str, Any]:
    return {
        "anchors": _collect_anchors(),
        "dispatcher": _collect_dispatcher(),
        "activity_feed": _collect_activity_feed(tail_n),
        "guard_violations": _collect_guard_violations(tail_n),
        "proof_packs": _collect_proof_packs(packs_n),
    }


def print_dashboard(summary: dict[str, Any]) -> None:
    anchors = summary["anchors"]
    dispatcher = summary["dispatcher"]
    feed = summary["activity_feed"]
    viol = summary["guard_violations"]
    packs = summary["proof_packs"]

    print("== Mission Control Viewer v0 (Read-Only) ==")
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

    print("\n[3] Linter Status")
    print("Use: python3 tools/ops/activity_feed_linter.py --json")

    print("\n[4] Activity Feed Tail")
    print(f"path: {feed['path']}")
    print(f"tail_count: {feed['summary']['count_tail']}")
    print(f"by_action: {feed['summary']['by_action']}")
    print(f"by_status_badge: {feed['summary']['by_status_badge']}")

    print("\n[5] Guard Violations Tail")
    print(f"path: {viol['path']}")
    print(f"tail_count: {viol['summary']['count_tail']}")
    print(f"by_reason: {viol['summary']['by_reason']}")

    print("\n[6] Latest Proof Packs")
    for row in packs:
        print(f"- {row['mtime_utc']}  {row['name']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mission Control Viewer v0 (read-only)")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    parser.add_argument("--tail", type=int, default=30, help="Tail line count for logs")
    parser.add_argument("--packs", type=int, default=10, help="Number of latest proof packs to show")
    args = parser.parse_args()

    summary = collect_summary(tail_n=max(args.tail, 1), packs_n=max(args.packs, 1))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_dashboard(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
