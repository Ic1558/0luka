#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops import remediation_engine

CANONICAL_RUNTIME_ROOT = Path("/Users/icmini/0luka_runtime")
DEFAULT_INTERVAL_SECONDS = 10.0


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return CANONICAL_RUNTIME_ROOT


def _log_path(runtime_root: Path) -> Path:
    return runtime_root / "state" / "remediation_daemon.log"


def _write_log(runtime_root: Path, message: str) -> None:
    path = _log_path(runtime_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{_utc_now()}] {message}\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_cycle(*, runtime_root: Path | None = None) -> list[dict[str, object]]:
    resolved_runtime_root = runtime_root or _runtime_root()
    decisions = remediation_engine.run_once(runtime_root=resolved_runtime_root)
    summary = ", ".join(f"{item.get('decision')}:{item.get('target')}" for item in decisions) or "none"
    _write_log(resolved_runtime_root, f"evaluation cycle complete; decisions: {summary}")
    return decisions


def run_daemon(
    *,
    runtime_root: Path | None = None,
    interval: float = DEFAULT_INTERVAL_SECONDS,
    max_cycles: int | None = None,
) -> int:
    resolved_runtime_root = runtime_root or _runtime_root()
    sleep_seconds = max(interval, 0.1)
    cycles = 0
    _write_log(resolved_runtime_root, "remediation daemon started")

    try:
        while True:
            try:
                decisions = run_cycle(runtime_root=resolved_runtime_root)
                for decision in decisions:
                    print(json.dumps(decision, ensure_ascii=False))
            except Exception as exc:
                _write_log(resolved_runtime_root, f"evaluation cycle failed: {exc}")
                print(json.dumps({"error": f"remediation_daemon_cycle_failed:{exc}"}, ensure_ascii=False), file=sys.stderr)

            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                _write_log(resolved_runtime_root, "remediation daemon stopped")
                return 0
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        _write_log(resolved_runtime_root, "remediation daemon stopped")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the remediation engine as a persistent daemon.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run a single remediation cycle")
    mode.add_argument("--daemon", action="store_true", help="Run the remediation daemon loop")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS, help="Loop interval in seconds")
    args = parser.parse_args()

    try:
        runtime_root = _runtime_root()
        if args.once:
            _write_log(runtime_root, "remediation daemon started")
            decisions = run_cycle(runtime_root=runtime_root)
            for decision in decisions:
                print(json.dumps(decision, ensure_ascii=False))
            _write_log(runtime_root, "remediation daemon stopped")
            return 0
        return run_daemon(runtime_root=runtime_root, interval=args.interval)
    except KeyboardInterrupt:
        _write_log(_runtime_root(), "remediation daemon stopped")
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"remediation_daemon_failed:{exc}"}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
