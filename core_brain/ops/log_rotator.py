#!/usr/bin/env python3
import os
import time
import shutil
import glob
from pathlib import Path
from datetime import datetime, timedelta

class LogRotator:
    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        self.policies = {
            "observability/bridge/inbox": 7,       # 7 Days
            "observability/quarantine/tasks": 30,  # 30 Days
            "observability/notebook_ingest": 1,    # 1 Day (Ephemeral)
            "interface/inbox/tasks": 7             # 7 Days (Stale Input)
        }

    def rotate(self, dry_run: bool = False) -> list[str]:
        report = []
        for rel_path, days in self.policies.items():
            target_dir = self.root / rel_path
            if not target_dir.exists():
                report.append(f"Skipped {rel_path} (Not found)")
                continue

            cutoff = datetime.now() - timedelta(days=days)
            report.append(f"Scanning {rel_path} (Retention: {days} days)")

            # Scan for common log patterns
            files = list(target_dir.glob("*.json")) + \
                    list(target_dir.glob("*.yaml")) + \
                    list(target_dir.glob("*.log")) + \
                    list(target_dir.glob("*.md"))

            deleted_count = 0
            for f in files:
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime < cutoff:
                        if not dry_run:
                            f.unlink()
                        deleted_count += 1
                except Exception as e:
                    report.append(f"  Error deleting {f.name}: {e}")

            action = "Would delete" if dry_run else "Deleted"
            if deleted_count > 0:
                report.append(f"  -> {action} {deleted_count} files older than {cutoff.strftime('%Y-%m-%d')}")
            else:
                report.append("  -> No files expired.")

        return report

if __name__ == "__main__":
    # Standalone test
    im_here = Path(__file__).resolve().parent.parent.parent
    rotator = LogRotator(im_here)
    print("\n".join(rotator.rotate(dry_run=True)))
