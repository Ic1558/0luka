#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "ops" / "heartbeat_dropper.py"


def _run_dropper(root: Path, agent: str = "cole") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ROOT"] = str(root)
    return subprocess.run(
        ["python3", str(SCRIPT), "--agent", agent],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_heartbeat_dropper_creates_jsonl_and_latest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = _run_dropper(root)
        assert result.returncode == 0, result.stderr

        jsonl_path = root / "observability" / "agents" / "heartbeat.jsonl"
        latest_path = root / "observability" / "agents" / "heartbeat.latest.json"
        assert jsonl_path.exists(), jsonl_path
        assert latest_path.exists(), latest_path


def test_heartbeat_record_structure_and_constraints() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _run_dropper(root, agent="cole")

        jsonl_path = root / "observability" / "agents" / "heartbeat.jsonl"
        line = jsonl_path.read_text(encoding="utf-8").strip().splitlines()[-1]
        payload = json.loads(line)

        for key in ("ts_utc", "agent_id", "pid", "host", "state", "version"):
            assert key in payload
        assert payload["agent_id"] == "cole"
        assert isinstance(payload["pid"], int)
        assert payload["state"] == "idle"
        assert payload["version"] == "15.5.1"
        assert "/" + "Users/" not in payload.get("agent_id", "")

        latest_payload = yaml.safe_load((root / "observability" / "agents" / "heartbeat.latest.json").read_text(encoding="utf-8"))
        assert isinstance(latest_payload, dict)
        assert latest_payload["agent_id"] == "cole"


def test_append_only_two_runs_two_lines_and_no_tmp_left() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _run_dropper(root, agent="cole")
        _run_dropper(root, agent="cole")

        base = root / "observability" / "agents"
        jsonl_path = base / "heartbeat.jsonl"
        lines = [ln for ln in jsonl_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 2

        tmp_leftovers = list(base.glob(".heartbeat.*.tmp"))
        assert tmp_leftovers == []
