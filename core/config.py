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
    if not raw or not raw.strip():
        raise RuntimeError("LUKA_RUNTIME_ROOT is required (fail-closed)")
    return Path(raw).expanduser().resolve()


ROOT = _resolve_root()
RUNTIME_ROOT = _resolve_runtime_root()

CORE_DIR = ROOT / "core"
INTERFACE_DIR = ROOT / "interface"
OBSERVABILITY_DIR = ROOT / "observability"
ARTIFACTS_DIR = ROOT / "artifacts"
RUNTIME_STATE_DIR = RUNTIME_ROOT / "state"

INBOX = INTERFACE_DIR / "inbox"
OUTBOX_TASKS = INTERFACE_DIR / "outbox" / "tasks"
COMPLETED = INTERFACE_DIR / "completed"
REJECTED = INTERFACE_DIR / "rejected"

DISPATCH_LOG = OBSERVABILITY_DIR / "logs" / "dispatcher.jsonl"
DISPATCH_LATEST = OBSERVABILITY_DIR / "artifacts" / "dispatch_latest.json"
DISPATCH_HEARTBEAT = OBSERVABILITY_DIR / "artifacts" / "dispatcher_heartbeat.json"
DISPATCH_LEDGER = OBSERVABILITY_DIR / "artifacts" / "dispatch_ledger.json"

SCHEMA_REGISTRY = CORE_DIR / "contracts" / "v1" / "0luka_schemas.json"
VERIFY_DIR = CORE_DIR / "verify"

RETENTION_ACTIVITY = OBSERVABILITY_DIR / "activity" / "activity.jsonl"
POLICY_MEMORY_PATH = RUNTIME_STATE_DIR / "policy_memory.json"
LEGACY_POLICY_MEMORY_PATH = CORE_DIR / "state" / "policy_memory.json"

DEFAULT_WATCH_INTERVAL_SEC = 5
