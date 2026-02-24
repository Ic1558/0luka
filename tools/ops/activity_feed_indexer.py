#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import sys
import hashlib
import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Configuration
ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_FEED_PATH = ROOT / "observability/logs/activity_feed.jsonl"
ARCHIVE_DIR = ROOT / "observability/logs/archive"
INDEX_DIR = ROOT / "observability/logs/index"
BY_ACTION_DIR = INDEX_DIR / "by_action"
BY_RUN_DIR = INDEX_DIR / "by_run"
TS_RANGES_DIR = INDEX_DIR / "ts_ranges"
INDEX_HEALTH_PATH = INDEX_DIR / "index_health.json"

def get_ms(ev: Dict[str, Any]) -> int:
    ms = ev.get("ts_epoch_ms")
    if ms is not None and isinstance(ms, (int, float)):
        return int(ms)
    ts_str = ev.get("ts_utc")
    if ts_str:
        from datetime import datetime
        try:
            return int(datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp() * 1000)
        except: pass
    return 0

def build_index(feed_path: Path):
    # Setup dirs
    for d in [BY_ACTION_DIR, BY_RUN_DIR, TS_RANGES_DIR]:
        if d.exists(): shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    last_ms = 0
    anomalies_flagged = False
    current_feed_rel = str(feed_path.relative_to(ROOT)) if feed_path.is_relative_to(ROOT) else str(feed_path)
    max_indexed_offset = 0
    
    archive_files = sorted(list(ARCHIVE_DIR.glob("activity_feed.*.jsonl")))
    archive_files = [f for f in archive_files if not f.name.endswith(".index.jsonl")]
    all_files = archive_files + [feed_path]
    
    manifest = {}
    
    # Pre-scan for anomalies
    for fpath in all_files:
        if not fpath.exists(): continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                # Just check if string exists in file (faster)
                # But be careful with partial reads. We'll check first 100MB only if needed.
                for line in f:
                    if '"anomaly_type": "sequence_regression"' in line or '"anomaly_type": "historical_regression_acknowledged"' in line:
                        anomalies_flagged = True
                        break
                if anomalies_flagged: break
        except: pass

    for fpath in all_files:
        if not fpath.exists(): continue
        
        rel_path = str(fpath.relative_to(ROOT)) if fpath.is_relative_to(ROOT) else str(fpath)
        f_manifest = {
            "min_ts_ms": float('inf'),
            "max_ts_ms": float('-inf'),
            "count": 0,
            "sha256": hashlib.sha256(fpath.read_bytes()).hexdigest()
        }
        
        with open(fpath, "rb") as f:
            offset = 0
            line_no = 0
            while True:
                line_bytes = f.readline()
                if not line_bytes: break
                
                length = len(line_bytes)
                line_no += 1
                try:
                    ev = json.loads(line_bytes.decode('utf-8'))
                except:
                    offset += length
                    continue
                
                curr_ms = get_ms(ev)
                action = ev.get("action")
                run_id = ev.get("run_id")
                
                if curr_ms and last_ms and curr_ms < last_ms:
                    if not anomalies_flagged:
                        print(f"CRITICAL: monotonic regression detected at {rel_path}:{line_no} without anomaly flag. last={last_ms} curr={curr_ms}", file=sys.stderr)
                        sys.exit(1)
                
                if curr_ms:
                    last_ms = curr_ms
                    f_manifest["min_ts_ms"] = min(f_manifest["min_ts_ms"], float(curr_ms))
                    f_manifest["max_ts_ms"] = max(f_manifest["max_ts_ms"], float(curr_ms))
                
                f_manifest["count"] += 1
                
                if action:
                    idx_line = {"ms": curr_ms, "file": rel_path, "off": offset, "len": length}
                    with open(BY_ACTION_DIR / f"{action}.idx.jsonl", "a") as af:
                        af.write(json.dumps(idx_line) + "\n")
                    if rel_path == current_feed_rel:
                        max_indexed_offset = max(max_indexed_offset, offset + length)
                
                if run_id:
                    idx_line = {"ms": curr_ms, "file": rel_path, "off": offset, "len": length}
                    with open(BY_RUN_DIR / f"{run_id}.idx.jsonl", "a") as rf:
                        rf.write(json.dumps(idx_line) + "\n")
                    if rel_path == current_feed_rel:
                        max_indexed_offset = max(max_indexed_offset, offset + length)
                
                offset += length
        
        if f_manifest["count"] > 0:
            manifest[rel_path] = f_manifest

    with open(TS_RANGES_DIR / "manifest.json", "w") as mf:
        json.dump(manifest, mf, indent=2)

    result = {
        "status": "complete",
        "files_processed": len(all_files),
        "manifest_sha256": hashlib.sha256((TS_RANGES_DIR / "manifest.json").read_bytes()).hexdigest()
    }

    # Write index health file (Pack 10: Index Sovereignty Contract)
    ts_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "") + "Z"
    health = {
        "ts_utc": ts_now,
        "status": "healthy",
        "reason_if_unhealthy": None,
        "files_indexed": len(all_files),
        "last_rebuild_ts": ts_now,
        "feed_path": current_feed_rel,
        # feed_sha: truncated to 16 hex chars (collision-detection only; full sha may be added
        # as feed_sha_full in a future pack without breaking sovereign_loop parsing)
        "feed_sha": hashlib.sha256(feed_path.read_bytes()).hexdigest()[:16] if feed_path.exists() else "",
        "feed_size": feed_path.stat().st_size if feed_path.exists() else 0,
        "max_indexed_offset": max_indexed_offset,
    }
    tmp = INDEX_HEALTH_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(health, indent=2))
    tmp.replace(INDEX_HEALTH_PATH)

    print(json.dumps(result))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", help="Override feed path")
    parser.add_argument("--emit-event", action="store_true",
                        help="Emit index_rebuilt_after_rotation event to activity feed after rebuild")
    args = parser.parse_args()

    feed = Path(args.feed) if args.feed else DEFAULT_FEED_PATH
    build_index(feed)

    if args.emit_event:
        try:
            ts_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "") + "Z"
            event = json.dumps({
                "ts_utc": ts_now,
                "action": "index_rebuilt_after_rotation",
                "emit_mode": "runtime_auto",
                "triggered_by": "feed_rotated",
            })
            with open(DEFAULT_FEED_PATH, "a") as f:
                f.write(event + "\n")
        except Exception:
            pass
