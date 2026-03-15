from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_registry_lisa_executor_is_canonical_only() -> None:
    registry_path = REPO_ROOT / "core_brain" / "catalog" / "registry.yaml"
    raw = registry_path.read_text(encoding="utf-8")
    assert "tools/bridge/lisa_executor.py" not in raw
    data = yaml.safe_load(raw) or {}
    tools = data.get("tools") if isinstance(data, dict) else None
    assert isinstance(tools, list)
    entries = [t for t in tools if isinstance(t, dict) and t.get("id") == "lisa_executor"]
    assert len(entries) == 1
    assert entries[0].get("path") == "system/agents/lisa_executor.py"


def test_deprecated_lisa_executor_path_is_disabled() -> None:
    path = REPO_ROOT / "tools" / "bridge" / "lisa_executor.py"
    proc = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "No such file or directory" in proc.stderr


def test_router_lisa_intent_uses_canonical_executor_not_clec(monkeypatch) -> None:
    router_mod = importlib.reload(importlib.import_module("core.router"))
    captured: dict[str, object] = {}

    def _fake_lisa(task_spec):
        captured["task_spec"] = task_spec
        return {"status": "ok", "evidence": {"logs": [], "commands": ["ls -la"], "effects": []}}

    monkeypatch.setattr(router_mod, "_execute_canonical_lisa", _fake_lisa)
    router = router_mod.Router()
    task_spec = {
        "schema_version": "clec.v1",
        "task_id": "test-lisa-authority",
        "intent": "lisa.exec_shell",
        "lane": "lisa",
        "executor": "lisa",
        "ops": [{"type": "run", "command": "ls -la"}],
    }
    out = router.execute(task_spec)
    assert out.get("status") == "ok"
    assert isinstance(captured.get("task_spec"), dict)
    assert captured["task_spec"]["ops"][0]["command"] == "ls -la"


def test_router_fails_closed_when_canonical_lisa_executor_unavailable(monkeypatch) -> None:
    router_mod = importlib.reload(importlib.import_module("core.router"))

    def _broken_lisa(_task_spec):
        return {"status": "error", "reason": "lisa_executor_import_failed:simulated", "evidence": {}}

    monkeypatch.setattr(router_mod, "_execute_canonical_lisa", _broken_lisa)
    router = router_mod.Router()
    task_spec = {
        "schema_version": "clec.v1",
        "task_id": "test-lisa-authority-fail-closed",
        "intent": "lisa.exec_shell",
        "lane": "lisa",
        "executor": "lisa",
        "ops": [{"type": "run", "command": "ls -la"}],
    }
    out = router.execute(task_spec)
    assert out.get("status") == "error"
    assert "lisa_executor_import_failed" in str(out.get("reason") or "")


def test_bridge_mapping_preserves_ls_la_command_for_proof() -> None:
    from core.bridge import to_core_task

    mapped = to_core_task(
        {
            "id": "test-bridge-lisa-ls-la",
            "source": "antigravity",
            "author": "lisa",
            "intent": "lisa.exec_shell",
            "lane": "lisa",
            "executor": "lisa",
            "schema_version": "clec.v1",
            "ops": [{"op_id": "op1", "type": "run", "command": "ls -la"}],
            "created_at_utc": "2026-03-15T00:00:00Z",
        }
    )
    assert mapped["intent"] == "lisa.exec_shell"
    assert mapped["lane"] == "lisa"
    assert mapped["ops"][0]["command"] == "ls -la"


def test_phase1a_lisa_accepts_ls_la_and_rejects_git_status() -> None:
    import core.phase1a_resolver as p1a

    base = {
        "schema_version": "clec.v1",
        "task_id": "test-lisa-proof-001",
        "ts_utc": "2026-03-15T00:00:00Z",
        "author": "antigravity",
        "call_sign": "[Antigravity]",
        "root": "${ROOT}",
        "intent": "lisa.exec_shell",
        "lane": "lisa",
        "executor": "lisa",
        "ops": [{"op_id": "op1", "type": "run", "command": "ls -la"}],
    }
    p1a._validate_clec_task(dict(base))

    bad = dict(base)
    bad["ops"] = [{"op_id": "op1", "type": "run", "command": "git status"}]
    try:
        p1a._validate_clec_task(bad)
    except p1a.Phase1AResolverError as exc:
        assert "lisa unauthorized proof command" in str(exc)
    else:
        raise AssertionError("expected Phase1AResolverError for git status under lisa authority")


def test_lisa_launchd_runner_points_to_canonical_executor() -> None:
    runner = (REPO_ROOT / "tools" / "bridge" / "_launchd_lisa_executor_runner.zsh").read_text(encoding="utf-8")
    assert 'python3 "$ROOT/system/agents/lisa_executor.py" --root "$ROOT"' in runner
