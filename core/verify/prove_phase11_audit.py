#!/usr/bin/env python3
"""Phase 11 deterministic proof runner (Observer-Narrator)."""
from __future__ import annotations

import ast
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PHASE11_DIR = ROOT / "modules" / "activity_intelligence"

FORBIDDEN_IMPORTS = {"subprocess"}
FORBIDDEN_CALLS = {"system", "popen", "dispatch_one", "submit_task", "CLECExecutor", "Router"}


class ProofError(RuntimeError):
    pass


def _set_env(root: Path) -> Dict[str, str | None]:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: Dict[str, str | None]) -> None:
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _scan_ast_forbidden() -> None:
    py_files = sorted(PHASE11_DIR.rglob("*.py"))
    if not py_files:
        raise ProofError("phase11_module_missing")

    violations: List[str] = []
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".")[0]
                    if mod in FORBIDDEN_IMPORTS:
                        violations.append(f"{path}:import:{mod}")
            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                if mod in FORBIDDEN_IMPORTS:
                    violations.append(f"{path}:from:{mod}")
            elif isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name in FORBIDDEN_CALLS:
                    violations.append(f"{path}:call:{name}")

    if violations:
        raise ProofError("forbidden_execution_authority:" + ",".join(violations))


def _load_narrator_module():
    import core.config as cfg

    importlib.reload(cfg)
    mod = importlib.import_module("modules.activity_intelligence.core.narrator")
    return importlib.reload(mod)


def _current_root() -> Path:
    return Path(os.environ.get("ROOT", str(ROOT))).expanduser().resolve()


def _verify_append_only(narrator_mod) -> None:
    base = _current_root()
    events = base / "observability" / "events.jsonl"
    _append_jsonl(events, {"ts": "2026-02-10T00:00:00Z", "type": "execution.started", "task_id": "p11_1"})

    feed = base / "observability" / "activity_feed.jsonl"
    before = feed.stat().st_size if feed.exists() else 0
    narrator_mod.generate_activity_intelligence(limit=20, write_artifacts=True)
    mid = feed.stat().st_size if feed.exists() else 0
    narrator_mod.generate_activity_intelligence(limit=20, write_artifacts=True)
    after = feed.stat().st_size if feed.exists() else 0

    if not (mid > before and after > mid):
        raise ProofError("append_only_invariant_failed")


def _verify_leak_protection(narrator_mod) -> None:
    events = _current_root() / "observability" / "events.jsonl"
    _append_jsonl(
        events,
        {
            "ts": "2026-02-10T00:00:01Z",
            "type": "policy.sense.started",
            "message": "source=/Users/icmini/.secrets token=sk-ABCDEF1234567890123456",
        },
    )
    out = narrator_mod.generate_activity_intelligence(limit=20, write_artifacts=False)
    blob = json.dumps(out, ensure_ascii=False)
    if "/Users/" in blob or "sk-" in blob:
        raise ProofError("leak_protection_failed")


def _verify_no_command_channel(narrator_mod) -> None:
    events = _current_root() / "observability" / "events.jsonl"
    _append_jsonl(
        events,
        {
            "ts": "2026-02-10T00:00:02Z",
            "type": "policy.sentry.blocked",
            "message": "; rm -rf /",
            "intent": "try ; rm -rf /",
        },
    )
    out = narrator_mod.generate_activity_intelligence(limit=20, write_artifacts=False)
    signals = out.get("audit_signals", [])
    if not signals:
        raise ProofError("missing_audit_signal")
    if not any(s.get("schema_version") == "audit.signal.v1" for s in signals):
        raise ProofError("invalid_signal_schema")

    serialized = json.dumps(out, ensure_ascii=False)
    if "rm -rf" in serialized or ";" in serialized and "UNSAFE_INPUT_REDACTED" not in serialized:
        raise ProofError("command_channel_not_neutralized")


def run_proof() -> bool:
    with tempfile.TemporaryDirectory() as td:
        tmp_root = Path(td).resolve()
        old = _set_env(tmp_root)
        try:
            _scan_ast_forbidden()
            narrator = _load_narrator_module()
            narrator.static_guard()
            _verify_append_only(narrator)
            _verify_leak_protection(narrator)
            _verify_no_command_channel(narrator)
        finally:
            _restore_env(old)
    return True


def main() -> int:
    try:
        ok = run_proof()
        print("Phase 11 Proof result:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    except Exception as exc:
        print(f"Phase 11 Proof result: FAIL ({exc})")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
