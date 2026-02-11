#!/usr/bin/env python3
from __future__ import annotations

import json
import importlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from jsonschema import validate as jsonschema_validate

import core.router as router_mod
from core.outbox_writer import write_result_to_outbox
from core.phase1d_result_gate import gate_outbound_result
from core.router import _safe_rename, _write_audit


def _load_executor():
    # Re-import after ROOT env update so executor writes inside tempdir.
    mod = importlib.import_module("core.clec_executor")
    return importlib.reload(mod)


def test_e2e_clec_write_text() -> None:
    """Full pipeline: CLEC write_text -> evidence -> outbox"""
    old_root = os.environ.get("ROOT")
    old_0luka_root = os.environ.get("0LUKA_ROOT")
    old_outbox = os.environ.get("OUTBOX_ROOT")
    task = {
        "schema_version": "clec.v1",
        "task_id": "e2e_test_001",
        "ts_utc": "2026-02-08T12:00:00Z",
        "author": "codex",
        "call_sign": "[Codex]",
        "root": "${ROOT}",
        "intent": "E2E pipeline test",
        "ops": [
            {
                "op_id": "op1",
                "type": "write_text",
                "target_path": "artifacts/e2e_test.txt",
                "content": "hello from e2e",
            }
        ],
        "verify": [],
    }
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        os.environ["ROOT"] = str(root)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "interface/outbox/tasks").mkdir(parents=True, exist_ok=True)
        (root / "artifacts").mkdir(parents=True, exist_ok=True)

        executor = _load_executor()
        status, evidence = executor.execute_clec_ops(
            task["ops"],
            {},
            task.get("verify"),
            run_provenance={
                "task_id": task["task_id"],
                "author": task["author"],
                "tool": "CLECExecutor",
                "evidence_refs": [f"task:{task['task_id']}"],
            },
        )
        assert status == "ok", f"execute failed: {status}"
        assert "artifacts/e2e_test.txt" in evidence.get("hashes", {}), "missing hash"

        result = {
            "task_id": task["task_id"],
            "status": status,
            "summary": "e2e test complete",
            "outputs": {"json": {"written": True}, "artifacts": []},
            "evidence": evidence,
            "provenance": {
                "trace_id": task["task_id"],
                "started_at": task["ts_utc"],
                "ended_at": task["ts_utc"],
                "engine": {"name": "core", "version": "phase3", "host": "local"},
                "hashes": {"inputs_sha256": "test", "outputs_sha256": "test"},
            },
        }
        gated = gate_outbound_result(result)
        assert gated["status"] == "ok", f"gate demoted: {gated.get('status')}"
        assert "/Users/" not in str(gated), "hard path leak"

        map_path = root / "ref_map.yaml"
        map_path.write_text(
            "version: '1'\n"
            "hosts:\n"
            "  default:\n"
            f"    root: '{root}'\n"
            "refs:\n"
            "  'ref://interface/outbox': '${root}/interface/outbox'\n",
            encoding="utf-8",
        )
        outbox_path, envelope = write_result_to_outbox(gated, ref_map_path=str(map_path))
        assert outbox_path.exists(), "outbox file not created"
        content = outbox_path.read_text(encoding="utf-8")
        assert "/Users/" not in content, "hard path in outbox"
        assert "e2e_test_001" in content, "task_id missing"
        assert envelope["task_id"] == "e2e_test_001"
        print("test_e2e_clec_write_text: ok")

    if old_root is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = old_root
    if old_0luka_root is None:
        os.environ.pop("0LUKA_ROOT", None)
    else:
        os.environ["0LUKA_ROOT"] = old_0luka_root
    if old_outbox is None:
        os.environ.pop("OUTBOX_ROOT", None)
    else:
        os.environ["OUTBOX_ROOT"] = old_outbox


def test_e2e_clec_run_command() -> None:
    """Full pipeline: CLEC run -> stdout capture -> outbox"""
    old_root = os.environ.get("ROOT")
    old_0luka_root = os.environ.get("0LUKA_ROOT")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        os.environ["ROOT"] = str(root)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "interface/outbox/tasks").mkdir(parents=True, exist_ok=True)
        (root / "core/verify").mkdir(parents=True, exist_ok=True)

        task = {
            "schema_version": "clec.v1",
            "task_id": "e2e_run_001",
            "ts_utc": "2026-02-08T12:00:00Z",
            "author": "codex",
            "call_sign": "[Codex]",
            "root": "${ROOT}",
            "intent": "E2E run test",
            "ops": [{"op_id": "op1", "type": "run", "command": "git status"}],
            "verify": [],
        }

        executor = _load_executor()
        _status, evidence = executor.execute_clec_ops(
            task["ops"],
            {},
            task.get("verify"),
            run_provenance={
                "task_id": task["task_id"],
                "author": task["author"],
                "tool": "CLECExecutor",
                "evidence_refs": [f"task:{task['task_id']}"],
            },
        )
        assert len(evidence.get("logs", [])) > 0, "no logs captured"
        assert evidence["logs"][0].get("command") == "git status"
        print("test_e2e_clec_run_command: ok")

    if old_root is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = old_root
    if old_0luka_root is None:
        os.environ.pop("0LUKA_ROOT", None)
    else:
        os.environ["0LUKA_ROOT"] = old_0luka_root


def test_router_safe_rename_creates_parent_dirs() -> None:
    """Regression: os.rename must not crash when parent dir missing."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = root / "artifacts" / "tasks" / "open" / "t1.yaml"
        dst = root / "artifacts" / "tasks" / "rejected" / "t1.yaml"

        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("id: t1\n", encoding="utf-8")
        assert not dst.parent.exists(), "precondition: dst parent should not exist"

        ok = _safe_rename(str(src), str(dst))

        assert ok is True
        assert not src.exists()
        assert dst.exists()

        # missing source should fail cleanly
        ok2 = _safe_rename(str(src), str(dst))
        assert ok2 is False
        print("test_router_safe_rename_creates_parent_dirs: ok")


def test_audit_artifact_exists_on_ok() -> None:
    """Audit artifact must exist after successful pipeline run."""
    old_root = os.environ.get("ROOT")
    old_0luka_root = os.environ.get("0LUKA_ROOT")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["ROOT"] = str(root)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "observability/artifacts/router_audit").mkdir(parents=True, exist_ok=True)

        task_id = "audit_test_ok"
        audit_path = _write_audit(
            task_id=task_id,
            decision="ok",
            intent="test.audit",
            executor="codex",
        )

        assert os.path.exists(audit_path), "audit artifact not created"
        content = Path(audit_path).read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["schema_version"] == "router_audit_v1"
        assert data["task_id"] == task_id
        assert data["decision"] == "ok"
        print("test_audit_artifact_exists_on_ok: ok")
    if old_root is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = old_root
    if old_0luka_root is None:
        os.environ.pop("0LUKA_ROOT", None)
    else:
        os.environ["0LUKA_ROOT"] = old_0luka_root


def test_audit_artifact_on_failure() -> None:
    """Audit artifact must exist with decision=rejected on failure."""
    old_root = os.environ.get("ROOT")
    old_0luka_root = os.environ.get("0LUKA_ROOT")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["ROOT"] = str(root)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "observability/artifacts/router_audit").mkdir(parents=True, exist_ok=True)

        task_id = "audit_test_fail"
        audit_path = _write_audit(
            task_id=task_id,
            decision="rejected",
            reason="gates_failed",
            intent="test.audit",
            executor="codex",
        )

        content = Path(audit_path).read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["decision"] == "rejected"
        assert data["reason"] == "gates_failed"
        print("test_audit_artifact_on_failure: ok")
    if old_root is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = old_root
    if old_0luka_root is None:
        os.environ.pop("0LUKA_ROOT", None)
    else:
        os.environ["0LUKA_ROOT"] = old_0luka_root


def test_audit_no_hardpaths() -> None:
    """Audit payload must not contain /Users/ or file:///Users."""
    old_root = os.environ.get("ROOT")
    old_0luka_root = os.environ.get("0LUKA_ROOT")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["ROOT"] = str(root)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "observability/artifacts/router_audit").mkdir(parents=True, exist_ok=True)

        task_id = "audit_test_nopath"
        audit_path = _write_audit(
            task_id=task_id,
            decision="ok",
            resolved_refs=["ref://interface/inbox", "ref://artifacts"],
            evidence_paths=["evidence.logs[2]"],
        )

        content = Path(audit_path).read_text(encoding="utf-8")
        assert "/Users/" not in content, "hard path detected in audit"
        assert "file:///Users" not in content, "file URI hard path detected"
        print("test_audit_no_hardpaths: ok")
    if old_root is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = old_root
    if old_0luka_root is None:
        os.environ.pop("0LUKA_ROOT", None)
    else:
        os.environ["0LUKA_ROOT"] = old_0luka_root


def test_audit_written_before_outbox_on_ok_path() -> None:
    """In committed path, audit artifact must exist before outbox write call."""
    old_root = os.environ.get("ROOT")
    old_0luka_root = os.environ.get("0LUKA_ROOT")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        os.environ["ROOT"] = str(root)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "artifacts/tasks/open").mkdir(parents=True, exist_ok=True)
        (root / "artifacts/tasks/closed").mkdir(parents=True, exist_ok=True)
        (root / "artifacts/tasks/rejected").mkdir(parents=True, exist_ok=True)
        (root / "observability/artifacts/router_audit").mkdir(parents=True, exist_ok=True)
        (root / "artifacts/tasks/open/tk_order.yaml").write_text("id: tk_order\n", encoding="utf-8")

        calls = {"outbox_called": False}
        orig_gate = router_mod.gate_outbound_result
        orig_outbox = router_mod.write_result_to_outbox
        try:
            router_mod.gate_outbound_result = lambda rb: rb

            def _fake_outbox_write(rb):
                audit_file = root / "observability/artifacts/router_audit/tk_order.json"
                assert audit_file.exists(), "audit must be written before outbox"
                calls["outbox_called"] = True
                return root / "interface/outbox/tasks/tk_order.result.json", rb

            router_mod.write_result_to_outbox = _fake_outbox_write

            router = router_mod.Router()
            router.policy["verification"]["required_gates_for_commit"] = []
            task_spec = {
                "id": "tk_order",
                "intent": "code.review",
                "actor": {"proposer": "codex"},
                "verification": {"gates": []},
            }
            result_bundle = {
                "task_id": "tk_order",
                "status": "ok",
                "summary": "ok",
                "outputs": {"artifacts": []},
                "evidence": {"logs": [], "commands": [], "effects": []},
                "provenance": {"hashes": {}},
            }
            out = router.audit(task_spec, result_bundle)
            assert out.get("status") == "committed"
            assert calls["outbox_called"] is True
            print("test_audit_written_before_outbox_on_ok_path: ok")
        finally:
            router_mod.gate_outbound_result = orig_gate
            router_mod.write_result_to_outbox = orig_outbox

    if old_root is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = old_root
    if old_0luka_root is None:
        os.environ.pop("0LUKA_ROOT", None)
    else:
        os.environ["0LUKA_ROOT"] = old_0luka_root


def test_router_rejects_on_invalid_audit_payload() -> None:
    """Router.audit must fail-closed when emitted audit payload is schema-invalid."""
    old_root = os.environ.get("ROOT")
    old_0luka_root = os.environ.get("0LUKA_ROOT")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        os.environ["ROOT"] = str(root)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "artifacts/tasks/open").mkdir(parents=True, exist_ok=True)
        (root / "artifacts/tasks/rejected").mkdir(parents=True, exist_ok=True)
        (root / "artifacts/tasks/open/invalid_audit.yaml").write_text(
            "id: invalid_audit\n", encoding="utf-8"
        )

        router = router_mod.Router()
        router.policy["verification"]["required_gates_for_commit"] = []
        task_spec = {
            "id": "",
            "intent": "schema.invalid.audit",
            "actor": {"proposer": "codex"},
            "verification": {"gates": []},
        }
        result_bundle = {
            "task_id": "invalid_audit",
            "status": "ok",
            "summary": "ok",
            "outputs": {"artifacts": []},
            "evidence": {"logs": [], "commands": [], "effects": []},
            "provenance": {"hashes": {}},
        }
        out = router.audit(task_spec, result_bundle)
        assert out.get("status") == "rejected"
        assert "audit_write_failed:audit_schema_invalid" in str(out.get("reason", ""))
        print("test_router_rejects_on_invalid_audit_payload: ok")

    if old_root is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = old_root
    if old_0luka_root is None:
        os.environ.pop("0LUKA_ROOT", None)
    else:
        os.environ["0LUKA_ROOT"] = old_0luka_root


def test_audit_schema_conformance() -> None:
    """Emitted audit must conform to router_audit schema for all 3 decisions."""
    old_root = os.environ.get("ROOT")
    old_0luka_root = os.environ.get("0LUKA_ROOT")
    schema_path = Path(__file__).resolve().parents[2] / "interface/schemas/router_audit_v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["ROOT"] = str(root)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "observability/artifacts/router_audit").mkdir(parents=True, exist_ok=True)

        for decision in ("ok", "rejected", "error"):
            audit_path = _write_audit(
                task_id=f"schema_test_{decision}",
                decision=decision,
                reason="test" if decision != "ok" else "",
                intent="schema.conformance",
                executor="codex",
            )
            data = json.loads(Path(audit_path).read_text(encoding="utf-8"))
            jsonschema_validate(instance=data, schema=schema)

        print("test_audit_schema_conformance: ok")

    if old_root is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = old_root
    if old_0luka_root is None:
        os.environ.pop("0LUKA_ROOT", None)
    else:
        os.environ["0LUKA_ROOT"] = old_0luka_root


def test_audit_rejects_invalid_decision() -> None:
    """_write_audit must reject decision values not in enum."""
    old_root = os.environ.get("ROOT")
    old_0luka_root = os.environ.get("0LUKA_ROOT")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["ROOT"] = str(root)
        os.environ["0LUKA_ROOT"] = str(root)

        for bad_decision in ("partial", "canceled", "unknown", ""):
            try:
                _write_audit(
                    task_id=f"bad_{bad_decision or 'empty'}",
                    decision=bad_decision,
                    intent="reject.test",
                    executor="codex",
                )
                raise AssertionError(f"should have rejected decision={bad_decision!r}")
            except RuntimeError as exc:
                assert "audit_schema_invalid" in str(exc), f"wrong error: {exc}"

        print("test_audit_rejects_invalid_decision: ok")

    if old_root is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = old_root
    if old_0luka_root is None:
        os.environ.pop("0LUKA_ROOT", None)
    else:
        os.environ["0LUKA_ROOT"] = old_0luka_root


def main() -> int:
    test_e2e_clec_write_text()
    test_e2e_clec_run_command()
    test_router_safe_rename_creates_parent_dirs()
    test_audit_artifact_exists_on_ok()
    test_audit_artifact_on_failure()
    test_audit_no_hardpaths()
    test_audit_written_before_outbox_on_ok_path()
    test_router_rejects_on_invalid_audit_payload()
    test_audit_schema_conformance()
    test_audit_rejects_invalid_decision()
    print("test_e2e_clec_pipeline: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
