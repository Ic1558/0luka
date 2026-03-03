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
        raise RuntimeError(
            "LUKA_RUNTIME_ROOT is required (fail-closed). "
            "Set LUKA_RUNTIME_ROOT=/Users/icmini/0luka_runtime"
        )
    return Path(raw).expanduser().resolve()


ROOT = _resolve_root()
RUNTIME_ROOT = _resolve_runtime_root()

CORE_DIR = ROOT / "core"
INTERFACE_DIR = ROOT / "interface"
OBSERVABILITY_DIR = ROOT / "observability"   # repo-local: incidents, router_audit, run_provenance
ARTIFACTS_DIR = ROOT / "observability" / "artifacts"  # legacy alias
RUNTIME_STATE_DIR = RUNTIME_ROOT / "state"

# Runtime write paths (Phase 1: logs + artifacts → LUKA_RUNTIME_ROOT)
RUNTIME_LOGS_DIR = RUNTIME_ROOT / "logs"
RUNTIME_ARTIFACTS_DIR = RUNTIME_ROOT / "artifacts"

INBOX = INTERFACE_DIR / "inbox"
OUTBOX_TASKS = INTERFACE_DIR / "outbox" / "tasks"
COMPLETED = INTERFACE_DIR / "completed"
REJECTED = INTERFACE_DIR / "rejected"

DISPATCH_LOG = RUNTIME_LOGS_DIR / "dispatcher.jsonl"
DISPATCH_LATEST = RUNTIME_ARTIFACTS_DIR / "dispatch_latest.json"
DISPATCH_HEARTBEAT = RUNTIME_ARTIFACTS_DIR / "dispatcher_heartbeat.json"
DISPATCH_LEDGER = RUNTIME_ARTIFACTS_DIR / "dispatch_ledger.json"

SCHEMA_REGISTRY = CORE_DIR / "contracts" / "v1" / "0luka_schemas.json"
VERIFY_DIR = CORE_DIR / "verify"

RETENTION_ACTIVITY = RUNTIME_LOGS_DIR / "activity.jsonl"
POLICY_MEMORY_PATH = RUNTIME_STATE_DIR / "policy_memory.json"
LEGACY_POLICY_MEMORY_PATH = CORE_DIR / "state" / "policy_memory.json"

DEFAULT_WATCH_INTERVAL_SEC = 5
