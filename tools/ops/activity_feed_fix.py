#!/usr/bin/env python3
"""Activity Feed Fixer (governance-safe, fail-closed)."""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def run_fix(src: Path, dry_run: bool = False) -> int:
    ts = _utc_now_iso()
    # No hard paths: use relative logic or repo root
    root = Path.cwd()
    
    quarantine_base = root / "observability" / "quarantine" / "activity_feed"
    report_base = root / "observability" / "reports" / "activity_feed_fix"
    
    quarantine_path = quarantine_base / f"{ts}_activity_feed.jsonl"
    report_path = report_base / f"{ts}_fix.json"
    
    if not src.exists():
        print(f"❌ ERROR: Source {src} does not exist.")
        return 1

    sha_before = _sha256(src)
    
    valid_lines = []
    dropped_samples = []
    total_lines = 0
    first_bad_line = None
    
    with src.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            total_lines += 1
            row = line.strip()
            if not row:
                continue
            try:
                json.loads(row)
                valid_lines.append(line)
            except Exception:
                if first_bad_line is None:
                    first_bad_line = i
                if len(dropped_samples) < 5:
                    dropped_samples.append({"line": i, "content": row[:200]})

    dropped_count = total_lines - len(valid_lines)
    
    report = {
        "schema_version": "activity_feed_fix_v1",
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(src),
        "sha256_before": sha_before,
        "counts": {
            "total_lines": total_lines,
            "valid_lines": len(valid_lines),
            "dropped_lines": dropped_count,
        },
        "first_bad_line": first_bad_line,
        "dropped_samples": dropped_samples,
    }

    if dry_run:
        print("🧪 DRY RUN MODE - No changes made.")
        print(json.dumps(report, indent=2))
        return 0

    # 1. Quarantine
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, quarantine_path)
    
    # 2. Rewrite original (clean copy)
    with src.open("w", encoding="utf-8") as f:
        for line in valid_lines:
            f.write(line)
            
    sha_after = _sha256(src)
    report["sha256_after"] = sha_after
    report["quarantine_path"] = str(quarantine_path)
    
    # 3. Write report
    report_base.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
        
    print(f"✅ REMEDIATION COMPLETE")
    print(f"Original quarantined to: {quarantine_path}")
    print(f"Clean copy written to:   {src}")
    print(f"Fix report written to:   {report_path}")
    print(f"Dropped {dropped_count} invalid lines.")
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="Clean activity_feed.jsonl of invalid JSON lines.")
    parser.add_argument("--src", help="Path to activity_feed.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Audit only, do not modify.")
    args = parser.parse_args()

    # Default logic from SPEC
    src_path = args.src or os.environ.get("LUKA_ACTIVITY_FEED_JSONL", "observability/logs/activity_feed.jsonl")
    src = Path(src_path).resolve()
    
    sys.exit(run_fix(src, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
