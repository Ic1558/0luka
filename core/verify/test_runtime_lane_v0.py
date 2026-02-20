from __future__ import annotations

import json
import os
import subprocess
import importlib
from pathlib import Path

from core import runtime_lane


REPO_ROOT = Path(__file__).resolve().parents[2]


def _runner_ok(cmd: list[str], capture_output: bool = True, text: bool = True):
    return subprocess.CompletedProcess(cmd, 0, stdout="state = running", stderr="")


def _make_root(name: str) -> Path:
    root = REPO_ROOT / "tmp" / name
    if root.exists():
        subprocess.run(["rm", "-rf", str(root)], check=True)
    (root / "interface" / "inbox").mkdir(parents=True, exist_ok=True)
    (root / "interface" / "outbox" / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "interface" / "completed").mkdir(parents=True, exist_ok=True)
    (root / "observability" / "logs").mkdir(parents=True, exist_ok=True)
    (root / "observability" / "logs" / "activity_feed.jsonl").write_text("", encoding="utf-8")
    return root


def _cleanup(root: Path) -> None:
    subprocess.run(["rm", "-rf", str(root)], check=True)


def _set_env(root: Path) -> dict[str, str | None]:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _copy_fixture(root: Path) -> None:
    src = REPO_ROOT / "modules" / "nlp_control_plane" / "tests" / "phase9_vectors_v0.yaml"
    dst = root / "modules" / "nlp_control_plane" / "tests" / "phase9_vectors_v0.yaml"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _bind_submit_root(root: Path) -> None:
    submit_mod = importlib.import_module("core.submit")
    submit_mod = importlib.reload(submit_mod)
    submit_mod.ROOT = root
    submit_mod.INBOX = root / "interface" / "inbox"
    submit_mod.OUTBOX = root / "interface" / "outbox" / "tasks"
    submit_mod.COMPLETED = root / "interface" / "completed"
    runtime_lane.submit_task = submit_mod.submit_task


def test_runtime_lane_positive_submit() -> None:
    root = _make_root("phase9_runtime_lane_positive")
    old = _set_env(root)
    try:
        _copy_fixture(root)
        _bind_submit_root(root)
        out = runtime_lane.submit_from_text("Run safe command: git status", root=root, runner=_runner_ok)
        assert out["ok"] is True, json.dumps(out, ensure_ascii=False)
        assert out["status"] == "submit_accepted"
        assert out["intent"] == "ops.run_command_safe"
        inbox_rel = out["receipt"]["inbox_path"]
        assert (root / inbox_rel).exists()
    finally:
        _restore_env(old)
        _cleanup(root)


def test_runtime_lane_enqueue_submit() -> None:
    root = _make_root("phase9_runtime_lane_enqueue")
    old = _set_env(root)
    try:
        _copy_fixture(root)
        _bind_submit_root(root)
        out = runtime_lane.submit_from_text(
            "Submit task to inbox: write artifacts/hello.txt = ok",
            root=root,
            runner=_runner_ok,
        )
        assert out["ok"] is True, json.dumps(out, ensure_ascii=False)
        assert out["status"] == "submit_accepted"
        assert out["intent"] == "kernel.enqueue_task"
        assert out["task_spec"]["schema_version"] == "clec.v1"
    finally:
        _restore_env(old)
        _cleanup(root)


def test_runtime_lane_reject_fail_closed() -> None:
    root = _make_root("phase9_runtime_lane_fail_closed")
    old = _set_env(root)
    try:
        _copy_fixture(root)
        _bind_submit_root(root)
        before = list((root / "interface" / "inbox").glob("*.yaml"))
        out = runtime_lane.submit_from_text("ลบไฟล์ทั้งหมดในโปรเจกต์", root=root, runner=_runner_ok)
        assert out["ok"] is False
        assert out["expected_result"] == "needs_clarification"
        after = list((root / "interface" / "inbox").glob("*.yaml"))
        assert len(after) == len(before)
    finally:
        _restore_env(old)
        _cleanup(root)
