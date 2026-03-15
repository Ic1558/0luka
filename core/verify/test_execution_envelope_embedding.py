from __future__ import annotations

import json
import os
from pathlib import Path

_runtime_root = Path(__file__).resolve().parents[2] / "0luka_runtime"
os.environ.setdefault("LUKA_RUNTIME_ROOT", str(_runtime_root))
_runtime_root.mkdir(parents=True, exist_ok=True)

def _sample_task():
    return {
        "task_id": "task-embed",
        "author": "embed-test",
        "schema_version": "clec.v1",
        "intent": "lisa.exec_shell",
        "lane": "lisa",
        "executor": "lisa",
        "ops": [{"op_id": "op1", "type": "run", "command": "ls -la"}],
    }


def _sample_exec_result():
    return {"status": "ok", "evidence": {"logs": [], "commands": [], "effects": []}}


def _sample_envelope():
    return {"trace": {"trace_id": "task-embed", "ts": "2026-03-15T00:00:00Z"}}


def test_result_bundle_embeds_execution_envelope():
    from core.task_dispatcher import _build_result_bundle

    task = _sample_task()
    bundle = _build_result_bundle(task["task_id"], _sample_envelope(), task, _sample_exec_result())
    envelope = bundle.get("execution_envelope")
    assert isinstance(envelope, dict)
    assert envelope.get("v") == "0luka.execution_envelope/v1"
    assert envelope.get("trace_id") == "task-embed"
    assert envelope.get("intent", {}).get("name") == "lisa.exec_shell"
    assert envelope.get("evidence", {}).get("execution_events")
    assert envelope.get("provenance", {}).get("outputs_sha256")
    assert envelope.get("provenance", {}).get("outputs_sha256") == bundle.get("provenance", {}).get("hashes", {}).get("outputs_sha256")


def test_outbox_envelope_preserves_execution_envelope(tmp_path: Path) -> None:
    from core.outbox_writer import _ensure_result_envelope

    task = _sample_task()
    result = {
        "task_id": task["task_id"],
        "status": "ok",
        "summary": "ok",
        "outputs": {"json": {}, "artifacts": []},
        "evidence": {
            "logs": [{"op_index": 0, "command": "ls -la", "returncode": 0}],
            "commands": ["ls -la"],
            "effects": [],
        },
        "trace_id": "task-embed",
        "provenance": {
            "hashes": {"inputs_sha256": "00", "outputs_sha256": ""},
        },
        "execution_envelope": {"v": "0luka.execution_envelope/v1", "seal": {"alg": "sha256", "value": "00"}},
    }
    envelope = _ensure_result_envelope(result)
    assert envelope.get("execution_envelope", {}).get("v") == "0luka.execution_envelope/v1"
    assert envelope["v"] == "0luka.result/v1"
    assert envelope["status"] == "ok"
