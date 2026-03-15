from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")

from core.outbox_writer import write_result_to_outbox
from core.task_dispatcher import _payload_sha256


def _basic_result(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "status": "ok",
        "summary": "phase0a execution",
        "trace_id": task_id,
        "outputs": {"json": {}, "artifacts": []},
        "evidence": {
            "logs": [json.dumps({"command": "ls -la", "returncode": 0}, ensure_ascii=False)],
            "commands": ["ls -la"],
            "effects": ["run:ls -la"],
        },
        "provenance": {"hashes": {"inputs_sha256": "", "outputs_sha256": ""}},
    }


def test_inputs_sha256_is_real_hash() -> None:
    task = {
        "task_id": "task_hash_001",
        "intent": "lisa.exec_shell",
        "schema_version": "clec.v1",
        "call_sign": "[Lisa]",
        "lane": "lisa",
        "executor": "lisa",
        "ops": [{"op_id": "op1", "type": "run", "command": "ls -la"}],
    }
    digest = _payload_sha256(task)
    assert digest != "dispatch"
    assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_outputs_sha256_generated_by_outbox_writer(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    outbox = tmp_path / "interface" / "outbox" / "tasks"
    outbox.mkdir(parents=True, exist_ok=True)

    old_env = {
        "OUTBOX_ROOT": os.environ.get("OUTBOX_ROOT"),
        "LUKA_RUNTIME_ROOT": os.environ.get("LUKA_RUNTIME_ROOT"),
    }
    os.environ["OUTBOX_ROOT"] = str(outbox.resolve())
    os.environ["LUKA_RUNTIME_ROOT"] = str(runtime.resolve())
    try:
        result = _basic_result("task_phase0a_outputs_001")
        path, envelope = write_result_to_outbox(result)

        hashes = envelope["provenance"]["hashes"]
        assert hashes["outputs_sha256"] != ""
        assert hashes["outputs_sha256"] != "dispatch"
        assert len(hashes["outputs_sha256"]) == 64

        assert envelope["v"] == "0luka.result/v1"
        assert "seal" in envelope
        assert "provenance" in envelope and "hashes" in envelope["provenance"]
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["provenance"]["hashes"]["outputs_sha256"] == hashes["outputs_sha256"]
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
