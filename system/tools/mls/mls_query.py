#!/usr/bin/env python3
"""
MLS query helper for agents.

Reads g/knowledge/mls_lessons.jsonl (JSON objects separated by newlines)
and exposes a small CLI:

  python3 system/tools/mls/mls_query.py summary
  python3 system/tools/mls/mls_query.py recent --limit 20 --type failure --format json
  python3 system/tools/mls/mls_query.py search --query "codex sandbox" --format table

This is read-only and has no side effects.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def repo_root() -> Path:
    root = Path(os.environ.get("ROOT", os.path.expanduser("~/0luka")))
    return root.resolve()


ROOT = repo_root()
MLS_FILE = ROOT / "g" / "knowledge" / "mls_lessons.jsonl"


def load_entries():
    """Load MLS entries from JSONL or pretty-printed JSON objects."""
    if not MLS_FILE.exists():
        return []

    content = MLS_FILE.read_text(encoding="utf-8").strip()
    if not content:
        return []

    parts = content.split("}\n{")
    json_objects = []
    if len(parts) == 1:
        json_objects = [content]
    else:
        for i, part in enumerate(parts):
            if i == 0:
                json_objects.append(part + "}")
            elif i == len(parts) - 1:
                json_objects.append("{" + part)
            else:
                json_objects.append("{" + part + "}")

    entries = []
    for raw in json_objects:
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        entries.append(
            {
                "id": entry.get("id", "MLS-UNKNOWN"),
                "type": entry.get("type", "other"),
                "title": entry.get("title", "Untitled"),
                "description": entry.get("description", ""),
                "context": entry.get("context", ""),
                "timestamp": entry.get("timestamp", ""),
                "related_wo": entry.get("related_wo") or entry.get("current_wo"),
                "related_session": entry.get("related_session") or entry.get("current_session"),
                "tags": entry.get("tags", []),
                "verified": bool(entry.get("verified", False)),
                "usefulness_score": entry.get("usefulness_score", 0),
                "source": entry.get("source", "unknown"),
            }
        )
    return entries


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Query MLS lessons for agents (read-only).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary", help="Show counts by type and verification.")

    recent = subparsers.add_parser("recent", help="Show most recent lessons.")
    recent.add_argument("--limit", type=int, default=20)
    recent.add_argument("--type", dest="type_filter", default="", help="Filter by type")
    recent.add_argument("--source", dest="source_filter", default="", help="Filter by source")
    recent.add_argument("--format", choices=["json", "table"], default="json")

    search = subparsers.add_parser("search", help="Search by substring in title/description/context.")
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--format", choices=["json", "table"], default="json")
    search.add_argument("--type", dest="type_filter", default="", help="Filter by type")

    return parser.parse_args(argv)


def cmd_summary(entries):
    by_type = {}
    verified = 0
    for entry in entries:
        t = entry.get("type", "other")
        by_type[t] = by_type.get(t, 0) + 1
        if entry.get("verified"):
            verified += 1

    out = {"total": len(entries), "verified": verified, "by_type": by_type}
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _parse_time(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def _sort_by_time(entries):
    return sorted(entries, key=lambda e: _parse_time(e.get("timestamp")) or datetime.min, reverse=True)


def _print_table(entries):
    for entry in entries:
        t = entry.get("timestamp") or "-"
        line = f"{entry.get('id','?')}\t{entry.get('type','other')}\t{t}\t{entry.get('title','Untitled')}"
        print(line)


def cmd_recent(entries, args):
    entries = _sort_by_time(entries)

    if args.type_filter:
        entries = [e for e in entries if e.get("type") == args.type_filter]
    if args.source_filter:
        entries = [e for e in entries if e.get("source") == args.source_filter]

    entries = entries[: args.limit]

    if args.format == "json":
        json.dump(entries, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        _print_table(entries)


def cmd_search(entries, args):
    q = args.query.lower()

    def matches(entry):
        haystack = " ".join([
            entry.get("title", ""),
            entry.get("description", ""),
            entry.get("context", ""),
        ]).lower()
        return q in haystack

    result = [e for e in entries if matches(e)]
    if args.type_filter:
        result = [e for e in result if e.get("type") == args.type_filter]
    result = _sort_by_time(result)[: args.limit]

    if args.format == "json":
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        _print_table(result)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    entries = load_entries()

    if args.command == "summary":
        cmd_summary(entries)
    elif args.command == "recent":
        cmd_recent(entries, args)
    elif args.command == "search":
        cmd_search(entries, args)
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
