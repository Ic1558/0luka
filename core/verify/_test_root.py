"""
_test_root.py — Single-source tmp ROOT setup helper for verify tests.

Usage:
    from core.verify._test_root import ensure_test_root
    ensure_test_root(root)   # call AFTER os.environ["ROOT"] = str(root)
"""
from __future__ import annotations

import importlib
import shutil
from pathlib import Path

# Real repo root (resolved at import time — always points to production tree)
_REAL_ROOT = Path(__file__).resolve().parents[2]


def ensure_test_root(root: Path) -> None:
    """Create standard directory layout + copy all interface/schemas into tmproot.

    Must be called AFTER setting os.environ["ROOT"] = str(root).
    Also reloads phase1a_resolver so its module-level ROOT constant
    picks up the new env value.
    """
    # Standard dirs
    (root / "interface" / "inbox").mkdir(parents=True, exist_ok=True)
    (root / "interface" / "outbox" / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "interface" / "completed").mkdir(parents=True, exist_ok=True)
    (root / "interface" / "rejected").mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / "tasks" / "open").mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / "tasks" / "closed").mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / "tasks" / "rejected").mkdir(parents=True, exist_ok=True)
    (root / "observability" / "artifacts" / "router_audit").mkdir(parents=True, exist_ok=True)
    (root / "observability" / "logs").mkdir(parents=True, exist_ok=True)
    (root / "core" / "contracts" / "v1").mkdir(parents=True, exist_ok=True)

    # Copy all schemas from real interface/schemas/ -> tmproot/interface/schemas/
    src_schemas = _REAL_ROOT / "interface" / "schemas"
    dst_schemas = root / "interface" / "schemas"
    dst_schemas.mkdir(parents=True, exist_ok=True)
    if src_schemas.is_dir():
        for f in src_schemas.iterdir():
            if f.is_file():
                shutil.copy2(f, dst_schemas / f.name)

    # Copy core contracts needed by phase1a_resolver
    src_contracts = _REAL_ROOT / "core" / "contracts" / "v1"
    dst_contracts = root / "core" / "contracts" / "v1"
    if src_contracts.is_dir():
        for f in src_contracts.iterdir():
            if f.is_file():
                shutil.copy2(f, dst_contracts / f.name)

    # Directly patch phase1a_resolver module-level schema path attributes to
    # point at tmproot copies.  We do NOT reload the full module because that
    # leaves a stale ROOT in sys.modules after the tmpdir is cleaned up,
    # causing later tests in the same pytest run to fail with "schema not found".
    # Callers MUST call restore_test_root_modules() in their finally block to
    # undo these patches so subsequent tests see the real repo paths.
    try:
        import core.phase1a_resolver as _resolver
        _resolver.DEFAULT_CLEC_SCHEMA = root / "interface" / "schemas" / "clec_v1.yaml"
        _resolver.DEFAULT_ROUTING_FILE = root / "interface" / "schemas" / "phase1a_routing_v1.yaml"
        _resolver.DEFAULT_COMBINED_SCHEMA = root / "core" / "contracts" / "v1" / "0luka_schemas.json"
        _resolver.ROOT = root
    except Exception:
        pass  # best-effort; test will surface the real error if resolver is missing


def restore_test_root_modules() -> None:
    """Restore phase1a_resolver module-level paths back to production (real repo) values.

    MUST be called in every test's finally block after ensure_test_root() was used.
    """
    try:
        import core.phase1a_resolver as _resolver
        _resolver.ROOT = _REAL_ROOT
        _resolver.DEFAULT_CLEC_SCHEMA = _REAL_ROOT / "interface" / "schemas" / "clec_v1.yaml"
        _resolver.DEFAULT_ROUTING_FILE = _REAL_ROOT / "interface" / "schemas" / "phase1a_routing_v1.yaml"
        _resolver.DEFAULT_COMBINED_SCHEMA = _REAL_ROOT / "core" / "contracts" / "v1" / "0luka_schemas.json"
    except Exception:
        pass


def make_task(root: Path, **overrides) -> dict:
    """Return a minimal valid CLEC v1 task dict with all required fields.

    All required fields per interface/schemas/clec_v1.yaml:
        schema_version, task_id, ts_utc, author, call_sign, root, intent, ops

    Caller can override any field via kwargs.
    """
    base = {
        "schema_version": "clec.v1",
        "task_id": "task_test_000",
        "ts_utc": "2026-02-20T00:00:00Z",
        "author": "test",
        "call_sign": "[Test]",
        "root": "${ROOT}",
        "intent": "test.noop",
        "ops": [{"op_id": "op0", "type": "run", "command": "git status"}],
        "verify": [],
    }
    base.update(overrides)
    return base
