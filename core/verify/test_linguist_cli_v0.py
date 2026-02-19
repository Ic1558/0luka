from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_cli(input_text: str, *, root: Path, runner_mode: str = "ok") -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["ROOT"] = str(root)
    env["LINGUIST_CLI_RUNNER"] = runner_mode
    cmd = ["python3", "-m", "core.linguist_cli", "--input", input_text]
    return subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)


def test_cli_happy_path_vector_001() -> None:
    cp = _run_cli("Create file notes/today.txt with text 'hello team'", root=REPO_ROOT)
    assert cp.returncode == 0, cp.stderr or cp.stdout
    obj = json.loads(cp.stdout)
    assert obj["ok"] is True
    assert obj["intent"] == "ops.write_text"
    assert obj["slots"]["path"] == "notes/today.txt"
    assert obj["slots"]["content"] == "hello team"


def test_cli_fail_closed_delete_all() -> None:
    cp = _run_cli("ลบไฟล์ทั้งหมดในโปรเจกต์", root=REPO_ROOT)
    assert cp.returncode == 2, cp.stderr or cp.stdout
    obj = json.loads(cp.stdout)
    assert obj["expected_result"] == "needs_clarification"


def test_cli_preflight_fail_when_missing_activity_feed() -> None:
    temp_root = REPO_ROOT / "tmp" / "phase9_cli_preflight_root"
    if temp_root.exists():
        subprocess.run(["rm", "-rf", str(temp_root)], check=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    try:
        cp = _run_cli("Create file notes/today.txt with text 'hello team'", root=temp_root)
        assert cp.returncode != 0
        obj = json.loads(cp.stdout)
        assert "sentry_violation" in obj.get("error", "")
    finally:
        subprocess.run(["rm", "-rf", str(temp_root)], check=True)
