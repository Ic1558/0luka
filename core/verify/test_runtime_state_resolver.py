from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.runtime.runtime_state_resolver import (  # noqa: E402
    RuntimeStateResolver,
    resolve_runtime_root,
)


def test_resolver_returns_canonical_state_paths(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(parents=True)
    resolver = RuntimeStateResolver(runtime_root)
    assert resolver.state_dir() == runtime_root / "state"
    assert resolver.qs_runs_dir() == runtime_root / "state" / "qs_runs"
    assert resolver.current_system_file() == runtime_root / "state" / "current_system.json"


def test_paths_are_under_runtime_root(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(parents=True)
    resolver = RuntimeStateResolver(runtime_root)
    for path in [
        resolver.state_dir(),
        resolver.qs_runs_dir(),
        resolver.current_system_file(),
        resolver.alerts_file(),
        resolver.approval_actions_file(),
        resolver.approval_log_file(),
    ]:
        assert str(path).startswith(str(runtime_root.resolve()))


def test_resolve_runtime_root_requires_existing_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LUKA_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("RUNTIME_ROOT", raising=False)
    try:
        resolve_runtime_root()
    except RuntimeError as exc:
        assert str(exc) == "runtime_root_missing"
    else:
        raise AssertionError("expected runtime_root_missing")

    bad = tmp_path / "missing"
    try:
        resolve_runtime_root(bad)
    except RuntimeError as exc:
        assert str(exc).startswith("runtime_root_not_found:")
    else:
        raise AssertionError("expected runtime_root_not_found")


def test_no_direct_runtime_state_string_paths_in_migrated_modules() -> None:
    migrated_files = [
        REPO_ROOT / "runtime" / "runtime_service.py",
        REPO_ROOT / "interface" / "operator" / "mission_control_server.py",
    ]
    forbidden = [
        '/ "state" / "qs_runs"',
        '/ "state" / "current_system.json"',
        "/Users/icmini/0luka_runtime",
    ]
    for file_path in migrated_files:
        content = file_path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in content
