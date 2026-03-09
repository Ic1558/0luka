#!/usr/bin/env python3
import os
import sys
import json
import time
import random
import argparse
import shutil
from pathlib import Path

# Defaults
DEFAULT_FEED_PATH = "observability/logs/activity_feed.jsonl"
LOCK_STALE_SEC = 30
LOCK_MAX_WAIT_MS = 1200
LOCK_INITIAL_BACKOFF_MS = 20
LOCK_MAX_BACKOFF_MS = 200
LOCK_JITTER_MS = 30
ROOT = Path(__file__).resolve().parents[2]

def check_stale_lock(lock_dir: Path) -> bool:
    """Checks if a lock is stale and removes it if safe to do so. Returns True if removed."""
    if not lock_dir.exists():
        return False
    
    pid_file = lock_dir / "pid"
    pid = None
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
        except ValueError:
            pass

    is_alive = True
    if pid is not None:
        try:
            os.kill(pid, 0)
        except OSError:
            is_alive = False
    else:
        # If no pid file, we just rely on mtime
        is_alive = False

    if not is_alive:
        try:
            mtime = lock_dir.stat().st_mtime
            age = time.time() - mtime
            if age > LOCK_STALE_SEC:
                # Remove stale lock
                shutil.rmtree(lock_dir, ignore_errors=True)
                return True
        except Exception:
            pass
            
    return False

def print_result(ok, appended, reason, attempts, wait_ms, feed_path):
    print(json.dumps({
        "ok": ok,
        "appended": appended,
        "reason": reason,
        "attempts": attempts,
        "wait_ms": wait_ms,
        "feed": str(feed_path)
    }))

def main():
    parser = argparse.ArgumentParser(description="Universal Activity Feed Append Helper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", help="JSON string payload")
    group.add_argument("--file", help="Path to JSON file payload")
    parser.add_argument("--feed", help="Path to feed file (overrides LUKA_ACTIVITY_FEED_JSONL)")
    parser.add_argument("--strict", action="store_true", help="Exit 1 instead of 2 on lock contention")
    args = parser.parse_args()

    # Determine feed path
    if args.feed:
        feed_path_str = args.feed
    else:
        # Determine from env var, handling the case where 0luka is executed in various ways
        feed_path_str = os.environ.get('LUKA_ACTIVITY_FEED_JSONL')
        if not feed_path_str:
            repo_root = os.environ.get("REPO_ROOT", "/Users/icmini/0luka")
            feed_path_str = os.path.join(repo_root, DEFAULT_FEED_PATH)
            
    feed_path = Path(feed_path_str).resolve()
    lock_dir = Path(f"{feed_path}.lock.d")
    
    # Parse payload
    payload_str = ""
    if args.json:
        payload_str = args.json
    elif args.file:
        try:
            payload_str = Path(args.file).read_text()
        except Exception as e:
            print_result(False, False, f"io_error_reading_file: {e}", 0, 0, feed_path)
            sys.exit(4)

    try:
        payload = json.loads(payload_str)
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")
    except Exception as e:
        print_result(False, False, f"invalid_json: {e}", 0, 0, feed_path)
        sys.exit(3)

    # Acquire lock
    start_ns = time.monotonic_ns()
    attempts = 0
    backoff = LOCK_INITIAL_BACKOFF_MS
    
    feed_path.parent.mkdir(parents=True, exist_ok=True)

    acquired = False
    reason = "ok"
    
    while True:
        attempts += 1
        try:
            lock_dir.mkdir()
            # Write pid
            (lock_dir / "pid").write_text(str(os.getpid()))
            acquired = True
            break
        except FileExistsError:
            if check_stale_lock(lock_dir):
                reason = "stale_lock_recovered"
                continue # Try to mkdir again immediately

        now_ns = time.monotonic_ns()
        wait_ms = (now_ns - start_ns) // 1000000
        
        if wait_ms >= LOCK_MAX_WAIT_MS:
            reason = "lock_contention"
            break
            
        jitter = random.randint(0, LOCK_JITTER_MS)
        sleep_ms = backoff + jitter
        time.sleep(sleep_ms / 1000.0)
        
        backoff = min(LOCK_MAX_BACKOFF_MS, backoff * 2)

    wait_ms = (time.monotonic_ns() - start_ns) // 1000000

    if not acquired:
        print_result(False, False, reason, attempts, wait_ms, feed_path)
        sys.exit(1 if args.strict else 2)

    # Append
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from core.activity_feed_guard import CANONICAL_PRODUCTION_FEED_PATH, guarded_append_activity_feed

        if not guarded_append_activity_feed(feed_path, payload):
            print_result(False, False, "guard_rejected", attempts, wait_ms, CANONICAL_PRODUCTION_FEED_PATH)
            shutil.rmtree(lock_dir, ignore_errors=True)
            sys.exit(4)
        print_result(True, True, reason, attempts, wait_ms, CANONICAL_PRODUCTION_FEED_PATH)
    except Exception as e:
        print_result(False, False, f"io_error_writing: {e}", attempts, wait_ms, feed_path)
        shutil.rmtree(lock_dir, ignore_errors=True)
        sys.exit(4)

    # Release lock
    shutil.rmtree(lock_dir, ignore_errors=True)
    sys.exit(0)

if __name__ == "__main__":
    main()
