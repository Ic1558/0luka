#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import qs_runtime_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply QS approval decisions to runtime state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--run-id", required=True)
    approve_parser.add_argument("--actor", required=True)
    approve_parser.add_argument("--reason")

    reject_parser = subparsers.add_parser("reject")
    reject_parser.add_argument("--run-id", required=True)
    reject_parser.add_argument("--actor", required=True)
    reject_parser.add_argument("--reason")

    args = parser.parse_args()

    try:
        if args.command == "approve":
            payload = qs_runtime_state.approve_run(args.run_id, actor=args.actor, reason=args.reason)
        else:
            payload = qs_runtime_state.reject_run(args.run_id, actor=args.actor, reason=args.reason)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 1

    print(json.dumps({"ok": True, "run": payload}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
