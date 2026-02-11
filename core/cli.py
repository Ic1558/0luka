#!/usr/bin/env python3
"""Unified CLI for kernel operations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from core import health as health_mod
from core import ledger as ledger_mod
from core import retention as retention_mod
from core import submit as submit_mod
from core import task_dispatcher as dispatcher_mod


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _cmd_status(args: argparse.Namespace) -> int:
    report = health_mod.check_health(run_tests=False)
    recent = ledger_mod.query()
    tail = recent[-int(args.tail):] if args.tail > 0 else []
    payload = {
        "schema_version": "core_cli_status_v1",
        "health": report,
        "queues": report.get("queues", {}),
        "recent_dispatches": tail,
    }
    if args.json:
        _print_json(payload)
    else:
        print("0luka Status")
        print("=" * 40)
        print(f"health: {report.get('status', 'unknown')}")
        queues = report.get("queues", {})
        print(
            "queues:"
            f" inbox={queues.get('inbox_pending', 0)}"
            f" completed={queues.get('completed', 0)}"
            f" rejected={queues.get('rejected', 0)}"
            f" outbox={queues.get('outbox_results', 0)}"
        )
        print(f"recent_dispatches: {len(tail)}")
        for row in tail:
            print(f"- {row.get('task_id', '')} [{row.get('status', '')}] {row.get('ts', '')}")
    return 0


def _cmd_submit(args: argparse.Namespace) -> int:
    if not args.file:
        print(json.dumps({"status": "error", "reason": "missing --file"}))
        return 1
    path = Path(args.file)
    if not path.exists() or not path.is_file():
        print(json.dumps({"status": "error", "reason": "file_not_found"}))
        return 1

    if path.suffix in (".yaml", ".yml") and submit_mod.yaml is not None:
        task = submit_mod.yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        task = json.loads(path.read_text(encoding="utf-8"))

    try:
        receipt = submit_mod.submit_task(task, task_id=args.task_id)
    except submit_mod.SubmitError as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}))
        return 1

    if args.json:
        _print_json(receipt)
    else:
        print(f"submitted: {receipt['task_id']}")
    return 0


def _cmd_dispatch(args: argparse.Namespace) -> int:
    if args.watch:
        dispatcher_mod.watch(interval=args.interval)
        return 0

    if args.file:
        result = dispatcher_mod.dispatch_one(Path(args.file), dry_run=args.dry_run)
        _print_json(result)
        return 0 if result.get("status") in ("committed", "skipped", "dry_run_ok") else 1

    results = dispatcher_mod.dispatch_all(dry_run=args.dry_run)
    if args.json:
        _print_json(results)
    else:
        for item in results:
            print(json.dumps(item, ensure_ascii=False))
    failed = sum(1 for item in results if item.get("status") == "error")
    return 1 if failed else 0


def _cmd_health(args: argparse.Namespace) -> int:
    report = health_mod.check_health(run_tests=args.full)
    if args.json:
        _print_json(report)
    else:
        health_mod._print_human(report)  # keep same output shape as existing health command
    return 0 if report.get("status") == "healthy" else 1


def _cmd_ledger(args: argparse.Namespace) -> int:
    if args.rebuild:
        data = ledger_mod.rebuild_from_log()
        if args.json:
            _print_json(data)
        else:
            ledger_mod._print_human(data.get("entries", []), data.get("summary", {}))
        return 0

    entries = ledger_mod.query(since=args.since, status=args.status)
    if args.tail and args.tail > 0:
        entries = entries[-args.tail :]
    data = {"entries": entries}
    if args.json:
        data["summary"] = ledger_mod._load_ledger().get("summary", {})
        _print_json(data)
    else:
        ledger_mod._print_human(entries, ledger_mod._load_ledger().get("summary", {}))
    return 0


def _cmd_retention(args: argparse.Namespace) -> int:
    dry_run = not args.apply
    summary = retention_mod.run_retention(dry_run=dry_run)
    if args.json:
        _print_json(summary)
    else:
        retention_mod._print_human(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m core", description="0luka unified core CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Composite health + queues + recent dispatches")
    p_status.add_argument("--tail", type=int, default=5, help="How many recent dispatches to show")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=_cmd_status)

    p_submit = sub.add_parser("submit", help="Submit task into inbox")
    p_submit.add_argument("--file", type=str, required=True, help="Task YAML/JSON file")
    p_submit.add_argument("--task-id", type=str, default=None)
    p_submit.add_argument("--json", action="store_true")
    p_submit.set_defaults(func=_cmd_submit)

    p_dispatch = sub.add_parser("dispatch", help="Run dispatcher")
    p_dispatch.add_argument("--file", type=str, help="Dispatch one task file")
    p_dispatch.add_argument("--watch", action="store_true")
    p_dispatch.add_argument("--interval", type=int, default=dispatcher_mod.DEFAULT_INTERVAL)
    p_dispatch.add_argument("--dry-run", action="store_true")
    p_dispatch.add_argument("--json", action="store_true")
    p_dispatch.set_defaults(func=_cmd_dispatch)

    p_health = sub.add_parser("health", help="Run health report")
    p_health.add_argument("--full", action="store_true")
    p_health.add_argument("--json", action="store_true")
    p_health.set_defaults(func=_cmd_health)

    p_ledger = sub.add_parser("ledger", help="Query dispatch ledger")
    p_ledger.add_argument("--since", type=str, default=None)
    p_ledger.add_argument("--status", type=str, default=None)
    p_ledger.add_argument("--tail", type=int, default=20)
    p_ledger.add_argument("--rebuild", action="store_true")
    p_ledger.add_argument("--json", action="store_true")
    p_ledger.set_defaults(func=_cmd_ledger)

    p_retention = sub.add_parser("retention", help="Run retention")
    p_retention.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete/rotate (default is dry-run preview)",
    )
    p_retention.add_argument("--json", action="store_true")
    p_retention.set_defaults(func=_cmd_retention)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

