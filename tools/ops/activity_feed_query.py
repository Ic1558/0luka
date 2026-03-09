#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import subprocess
import sys
import argparse
import time
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from core.config import RUNTIME_ROOT  # single source — fail-closed enforced in core.config

ROOT = _REPO_ROOT

INDEX_DIR = RUNTIME_ROOT / "logs/index"
INDEX_HEALTH_PATH = INDEX_DIR / "index_health.json"
INDEXER = Path(__file__).parent / "activity_feed_indexer.py"
BY_OUTCOME_DIR = INDEX_DIR / "by_outcome"
PROVENANCE_INDEX_DIR = INDEX_DIR / "provenance"

PROVENANCE_PATH = ROOT / "observability" / "artifacts" / "run_provenance.jsonl"

def load_index_lines(path: Path) -> List[Dict[str, Any]]:
    if not path.exists(): return []
    res = []
    with open(path, "r") as f:
        for line in f:
            try: res.append(json.loads(line))
            except: continue
    return res

def _has_stale_offsets(candidates: List[Dict[str, Any]]) -> bool:
    """Return True if any candidate points past its file's current size."""
    for c in candidates:
        f_path = ROOT / c["file"]
        try:
            if not f_path.exists() or c["off"] + c["len"] > f_path.stat().st_size:
                return True
        except OSError:
            return True
    return False


def _trigger_index_rebuild() -> bool:
    """Run the indexer synchronously. Returns True on success."""
    try:
        subprocess.run([sys.executable, str(INDEXER)], timeout=60,
                       capture_output=True, check=True)
        return True
    except Exception:
        return False


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

    # Pack 10: Assert index_max_offset <= file_size; auto-rebuild if stale.
    auto_rebuilt = False
    if candidates and _has_stale_offsets(candidates):
        if _trigger_index_rebuild():
            # Reload candidates from freshly rebuilt index
            if action:
                candidates = load_index_lines(INDEX_DIR / "by_action" / f"{action}.idx.jsonl")
            elif run_id:
                candidates = load_index_lines(INDEX_DIR / "by_run" / f"{run_id}.idx.jsonl")
            auto_rebuilt = True

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
        "auto_rebuilt": auto_rebuilt,
        "files_scanned": 0,
        "indices_used": 1,
        "results": results
    }


def _load_provenance_index() -> Dict[str, Dict[str, Any]]:
    idx_path = PROVENANCE_INDEX_DIR / "by_trace_id.idx.jsonl"
    mapping: Dict[str, Dict[str, Any]] = {}
    for item in load_index_lines(idx_path):
        trace = str(item.get("trace_id") or "").strip()
        if trace:
            mapping[trace] = item
    return mapping


def _read_json_line_at(path: Path, off: int, length: int) -> Dict[str, Any] | None:
    try:
        with open(path, "rb") as f:
            f.seek(off)
            line = f.read(length)
        ev = json.loads(line.decode("utf-8"))
        return ev if isinstance(ev, dict) else None
    except Exception:
        return None


def query_decision_history(n: int = 10, status: str | None = None) -> List[Dict[str, Any]]:
    """
    Returns recent decision/execution history records joined with run_provenance by trace_id when possible.
    This is a bounded read-only query over existing authoritative surfaces.
    """
    status_value = str(status).strip().lower() if status is not None else None
    if status_value == "":
        status_value = None

    candidates: List[Dict[str, Any]] = []
    if status_value:
        idx_path = BY_OUTCOME_DIR / f"{status_value}.jsonl"
        candidates = load_index_lines(idx_path)
    else:
        for idx_path in sorted(BY_OUTCOME_DIR.glob("*.jsonl")):
            candidates.extend(load_index_lines(idx_path))

    if not candidates:
        return []

    candidates.sort(key=lambda x: int(x.get("ms") or 0))
    picked = candidates[-int(n) :] if len(candidates) > int(n) else candidates

    prov_index = _load_provenance_index()
    results: List[Dict[str, Any]] = []

    for c in picked:
        file_rel = c.get("file")
        if not isinstance(file_rel, str) or not file_rel:
            continue
        f_path = ROOT / file_rel
        try:
            if not f_path.exists() or int(c.get("off") or 0) + int(c.get("len") or 0) > f_path.stat().st_size:
                continue
        except OSError:
            continue

        ev = _read_json_line_at(f_path, int(c.get("off") or 0), int(c.get("len") or 0))
        if not ev:
            continue

        ev_status = ev.get("status")
        if status_value and str(ev_status or "").strip().lower() != status_value:
            # If index file is stale or event changed shape, fail-closed by skipping mismatch.
            continue

        record: Dict[str, Any] = {}
        for key in ("trace_id", "status", "ts_utc", "ts", "run_id", "task_id", "job_type", "project_id"):
            val = ev.get(key)
            if val is not None and str(val).strip() != "":
                record[key] = val

        trace = str(ev.get("trace_id") or "").strip()
        if trace and trace in prov_index:
            prov_ptr = prov_index[trace]
            prov_path = Path(str(prov_ptr.get("file") or PROVENANCE_PATH))
            prov = _read_json_line_at(prov_path, int(prov_ptr.get("off") or 0), int(prov_ptr.get("len") or 0))
            if isinstance(prov, dict):
                for key in ("run_id", "task_id", "job_type", "project_id"):
                    val = prov.get(key)
                    if val is not None and str(val).strip() != "" and key not in record:
                        record[key] = val
                if "trace_id" not in record and prov.get("trace_id"):
                    record["trace_id"] = prov.get("trace_id")

        results.append(record)

    return results

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
