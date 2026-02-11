#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COLE_RUN = REPO_ROOT / "cole" / "tools" / "cole_run.zsh"
RUN_TOOL = REPO_ROOT / "tools" / "run_tool.zsh"


def _run_cole(args, root: Path):
    env = os.environ.copy()
    env["COLE_RUN_ROOT"] = str(root)
    proc = subprocess.run(
        ["zsh", str(COLE_RUN), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def test_list_is_deterministic_sorted():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        runs = root / "cole" / "runs"
        runs.mkdir(parents=True)
        (runs / "run-20").mkdir()
        (runs / "run-01").mkdir()
        (runs / "run-10").mkdir()

        rc, out, _ = _run_cole(["list"], root)
        assert rc == 0, out
        payload = json.loads(out)
        assert payload["ok"] is True
        assert payload["runs"] == ["run-01", "run-10", "run-20"]


def test_latest_uses_explicit_max_rule():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        runs = root / "cole" / "runs"
        runs.mkdir(parents=True)
        (runs / "alpha").mkdir()
        (runs / "beta").mkdir()

        rc, out, _ = _run_cole(["latest"], root)
        assert rc == 0, out
        payload = json.loads(out)
        assert payload["ok"] is True
        assert payload["rule"] == "max(sorted_lexicographic)"
        assert payload["run_id"] == "beta"


def test_show_rejects_outside_scope_run_id():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "cole" / "runs").mkdir(parents=True)

        rc, out, _ = _run_cole(["show", "../../etc/passwd"], root)
        assert rc != 0
        payload = json.loads(out)
        assert payload["ok"] is False
        assert payload["error"] == "invalid_run_id"


def test_show_redacts_sensitive_content():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        runs = root / "cole" / "runs"
        runs.mkdir(parents=True)
        sample = runs / "run1.json"
        sample.write_text(
            "path=/Users/icmini/secret\\n"
            "token=ghp_abc123\\n"
            "auth=Authorization: Bearer supersecret\\n",
            encoding="utf-8",
        )

        rc, out, _ = _run_cole(["show", "run1"], root)
        assert rc == 0, out
        payload = json.loads(out)
        assert payload["ok"] is True
        assert "/Users/" not in payload["content"]
        assert "ghp_" not in payload["content"]
        assert "supersecret" not in payload["content"]


def test_no_write_or_network_patterns():
    text = COLE_RUN.read_text(encoding="utf-8")
    forbidden_write = ["touch ", "mkdir ", "rm ", "mv ", "cp ", ">>", "> "]
    forbidden_network = ["curl ", "wget ", "ssh ", "nc ", "telnet ", "http://", "https://"]

    for token in forbidden_write:
        assert token not in text, f"unexpected write pattern: {token}"
    for token in forbidden_network:
        assert token not in text, f"unexpected network pattern: {token}"


def test_run_tool_has_explicit_cole_delegate():
    text = RUN_TOOL.read_text(encoding="utf-8")
    assert "cole-run)" in text
    assert "zsh cole/tools/cole_run.zsh" in text


if __name__ == "__main__":
    test_list_is_deterministic_sorted()
    test_latest_uses_explicit_max_rule()
    test_show_rejects_outside_scope_run_id()
    test_show_redacts_sensitive_content()
    test_no_write_or_network_patterns()
    test_run_tool_has_explicit_cole_delegate()
    print("test_cole_run_integration: all ok")
