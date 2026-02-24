#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import sys
import argparse
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_DIR = ROOT / "observability/logs/index"

def load_index_lines(path: Path) -> List[Dict[str, Any]]:
    if not path.exists(): return []
    res = []
    with open(path, "r") as f:
        for line in f:
            try: res.append(json.loads(line))
            except: continue
    return res

def query(action=None, run_id=None, since_ms=None, until_ms=None, last_min=None, limit=200):
    now_ms = int(time.time() * 1000)
    if last_min:
        since_ms = now_ms - (last_min * 60 * 1000)

    candidates = []
    
    if action:
        idx_path = INDEX_DIR / "by_action" / f"{action}.idx.jsonl"
        candidates = load_index_lines(idx_path)
    elif run_id:
        idx_path = INDEX_DIR / "by_run" / f"{run_id}.idx.jsonl"
        candidates = load_index_lines(idx_path)
    else:
        # If no index key, we have to scan all manifests? 
        # Support only indexed queries for now as per contract.
        print("Error: Query must specify --action or --run-id for Pack 7.", file=sys.stderr)
        return {"ok": False, "error": "unindexed_query_not_supported"}

    # Filter candidates by time
    filtered = []
    for c in candidates:
        ms = c.get("ms", 0)
        if since_ms and ms < since_ms: continue
        if until_ms and ms > until_ms: continue
        filtered.append(c)
    
    # Sort by time
    filtered.sort(key=lambda x: x["ms"])
    
    # Take latest? Or earliest? Usually for "last-min" we want latest.
    # But usually feeds are chronological. I'll take all matches up to limit.
    last_n = filtered[-limit:] if len(filtered) > limit else filtered
    
    results = []
    files_opened = set()
    stale_skipped = 0

    for c in last_n:
        f_path = ROOT / c["file"]
        off = c["off"]
        length = c["len"]

        # Guard: skip stale index entries whose offsets exceed the current file size.
        # This happens when the feed is rotated but the index has not been rebuilt yet.
        try:
            if not f_path.exists() or off + length > f_path.stat().st_size:
                stale_skipped += 1
                continue
        except OSError:
            stale_skipped += 1
            continue

        try:
            with open(f_path, "rb") as f:
                f.seek(off)
                line = f.read(length)
                results.append(json.loads(line.decode('utf-8')))
                files_opened.add(str(f_path))
        except Exception as e:
            results.append({"error": f"read_failed_at_offset_{off}", "msg": str(e)})

    return {
        "ok": True,
        "query_mode": "index",
        "matched_count": len(filtered),
        "results_count": len(results),
        "stale_skipped": stale_skipped,
        "files_scanned": 0,
        "indices_used": 1,
        "results": results
    }

def main():
    parser = argparse.ArgumentParser(description="0luka Activity Feed Query (O(log n))")
    parser.add_argument("--action", help="Filter by action index")
    parser.add_argument("--run-id", help="Filter by run_id index")
    parser.add_argument("--last-min", type=int, help="Limit to last N minutes")
    parser.add_argument("--since-ms", type=int, help="Since epoch ms")
    parser.add_argument("--until-ms", type=int, help="Until epoch ms")
    parser.add_argument("--limit", type=int, default=200, help="Max results")
    parser.add_argument("--json", action="store_true", help="JSON output")
    
    args = parser.parse_args()
    
    res = query(
        action=args.action,
        run_id=args.run_id,
        since_ms=args.since_ms,
        until_ms=args.until_ms,
        last_min=args.last_min,
        limit=args.limit
    )
    
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"ok={res['ok']} matched={res['matched_count']} mode={res['query_mode']}")
        for r in res.get("results", []):
            print(json.dumps(r))

if __name__ == "__main__":
    main()
