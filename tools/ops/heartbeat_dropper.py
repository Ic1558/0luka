#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

VERSION = "15.5.1"


def _repo_root() -> Path:
    root_env = os.environ.get("ROOT", "").strip()
    if root_env:
        return Path(root_env).expanduser().resolve(strict=False)
    return Path(__file__).resolve().parents[2]


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _heartbeat_paths(root: Path) -> tuple[Path, Path]:
    base = root / "observability" / "agents"
    return base / "heartbeat.jsonl", base / "heartbeat.latest.json"


def _build_record(agent_id: str, state: str) -> Dict[str, Any]:
    return {
        "ts_utc": _now_utc_iso(),
        "agent_id": agent_id,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "state": state,
        "version": VERSION,
    }


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def _write_latest_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write then rename to avoid partial pointer states.
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), prefix=".heartbeat.", suffix=".tmp", delete=False
    ) as tmp:
        tmp.write(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def write_heartbeat(agent_id: str, state: str, root: Path | None = None) -> Path:
    root_dir = root or _repo_root()
    jsonl_path, latest_path = _heartbeat_paths(root_dir)
    record = _build_record(agent_id=agent_id, state=state)
    _append_jsonl(jsonl_path, record)
    _write_latest_atomic(latest_path, record)
    return jsonl_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write heartbeat observability records")
    parser.add_argument("--agent", default="cole", help="Agent id")
    parser.add_argument("--state", default="idle", help="Agent state")
    parser.add_argument("--out", default=None, help="Output root (default: $ROOT or repo root)")
    args = parser.parse_args()

    try:
        root = Path(args.out).expanduser().resolve(strict=False) if args.out else _repo_root()
        jsonl_path = write_heartbeat(agent_id=args.agent, state=args.state, root=root)
        print(str(jsonl_path))
    except Exception as exc:  # observability should never crash caller
        print(f"heartbeat_dropper_non_fatal_error:{type(exc).__name__}:{exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
