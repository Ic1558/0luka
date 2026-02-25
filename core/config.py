#!/usr/bin/env python3
"""Kernel config: single source of truth for paths and constants."""
from __future__ import annotations

import os
from pathlib import Path


def _resolve_root() -> Path:
    raw = os.environ.get("ROOT")
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _resolve_runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT")
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()

    if os.environ.get("PYTEST_CURRENT_TEST"):
        import tempfile
        return Path(tempfile.mkdtemp(prefix="0luka_rt_"))

    raise RuntimeError(
        "LUKA_RUNTIME_ROOT is not set. "
        "Run bootstrap_runtime.zsh first."
    )


ROOT = _resolve_root()
RUNTIME_ROOT = _resolve_runtime_root()

CORE_DIR = ROOT / "core"
INTERFACE_DIR = ROOT / "interface"

# All observability and artifacts moved out of repo
OBSERVABILITY_DIR = RUNTIME_ROOT / "logs"
ARTIFACTS_DIR = RUNTIME_ROOT / "artifacts"

INBOX = INTERFACE_DIR / "inbox"
OUTBOX_TASKS = INTERFACE_DIR / "outbox" / "tasks"
COMPLETED = INTERFACE_DIR / "completed"
REJECTED = INTERFACE_DIR / "rejected"

DISPATCH_LOG = OBSERVABILITY_DIR / "dispatcher.jsonl"
DISPATCH_LATEST = ARTIFACTS_DIR / "dispatch_latest.json"
DISPATCH_HEARTBEAT = ARTIFACTS_DIR / "dispatcher_heartbeat.json"
DISPATCH_LEDGER = ARTIFACTS_DIR / "dispatch_ledger.json"

SCHEMA_REGISTRY = CORE_DIR / "contracts" / "v1" / "0luka_schemas.json"
VERIFY_DIR = CORE_DIR / "verify"

RETENTION_ACTIVITY = OBSERVABILITY_DIR / "activity.jsonl"
ACTIVITY_FEED_PATH = OBSERVABILITY_DIR / "activity_feed.jsonl"
VIOLATION_LOG_PATH = OBSERVABILITY_DIR / "feed_guard_violations.jsonl"

DEFAULT_WATCH_INTERVAL_SEC = 5
