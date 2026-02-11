#!/usr/bin/env python3
"""Phase 13 supervision tests: annotation sink + UI safety + no dispatcher calls."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANNOTATION_HANDLER = ROOT / "tools" / "ops" / "mission_control" / "annotation_handler.py"
SERVER_FILE = ROOT / "tools" / "ops" / "mission_control" / "server.py"
UI_FILE = ROOT / "tools" / "ops" / "mission_control" / "ui" / "index.html"

FORBIDDEN_TOKENS = [
    "core.task_dispatcher",
    "dispatch_one",
    "core/dispatch",
    "interface/inbox",
    "subprocess",
    "os.system",
]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to import: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def _set_root(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore(old: dict) -> None:
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_static_no_dispatcher_or_exec_calls() -> None:
    for path in (ANNOTATION_HANDLER, SERVER_FILE):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        src = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            if token in src and token not in {"interface/inbox", "core/dispatch"}:
                raise AssertionError(f"forbidden token in {path}: {token}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                assert name not in {"dispatch_one", "system", "popen"}, f"forbidden call in {path}: {name}"
    print("test_static_no_dispatcher_or_exec_calls: ok")


def test_annotation_append_and_schema_validation() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        old = _set_root(root)
        try:
            mod = _load_module(ANNOTATION_HANDLER, "annotation_handler_test")
            row = mod.append_annotation(
                {
                    "event_id": "evt-1",
                    "action": "acknowledge",
                    "comment": "Looks good",
                    "author": "user_admin",
                }
            )
            assert row["schema_version"] == "annotation.v1"
            path = root / "observability" / "annotations" / "annotations.jsonl"
            assert path.exists()
            lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
            assert len(lines) == 1

            try:
                mod.append_annotation(
                    {
                        "event_id": "evt-2",
                        "action": "note",
                        "comment": "; rm -rf /",
                        "author": "user_admin",
                    }
                )
                raise AssertionError("command-like comment must be rejected")
            except Exception:
                pass
            print("test_annotation_append_and_schema_validation: ok")
        finally:
            _restore(old)


def test_ui_has_ack_and_annotation_post_only() -> None:
    html = UI_FILE.read_text(encoding="utf-8")
    assert "Acknowledge" in html
    assert "/api/annotations" in html
    assert "fetch('/api/annotations'" in html
    assert "dispatch_one" not in html
    assert "interface/inbox" not in html
    print("test_ui_has_ack_and_annotation_post_only: ok")


def main() -> int:
    test_static_no_dispatcher_or_exec_calls()
    test_annotation_append_and_schema_validation()
    test_ui_has_ack_and_annotation_post_only()
    print("test_phase13_supervision: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
