#!/usr/bin/env python3
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _set_root(root: Path):
    old = os.environ.get("ROOT")
    os.environ["ROOT"] = str(root)
    return old


def _restore_root(old):
    if old is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = old


def _manifest_with_runtime_boundary_audit() -> str:
    return """# manifest

## Core-Brain Owned Skills (Phase 15)
| skill_id | purpose | Mandatory Read | MCPs used | Inputs | Outputs | Caps | Forbidden actions |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| `runtime_boundary_audit` | audit runtime boundaries | YES | fs | in | out | cap | forbid |

## Codex Hand Wiring Map (Phase 15.2)
| skill_id | required_preamble | caps_profile | max_retries | single_flight | no_parallel |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `runtime_boundary_audit` | `verify-first` | `read_assist_only` | 0 | true | true |
"""


def _skill_md() -> str:
    return """---
name: runtime_boundary_audit
description: test skill. Mandatory Read: YES
---

# Runtime Boundary Audit

Mandatory Read: YES
"""


def test_manifest_row_loads_without_wiring_error() -> None:
    wiring = importlib.import_module("core_brain.compiler.skill_wiring")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_runtime_boundary_audit())
        old = _set_root(root)
        try:
            rows = wiring.load_wiring_map(root / "skills" / "manifest.md")
            assert "runtime_boundary_audit" in rows
            row = rows["runtime_boundary_audit"]
            assert row.required_preamble == "verify-first"
            assert row.caps_profile == "read_assist_only"
            assert row.max_retries == 0
            assert row.single_flight is True
            assert row.no_parallel is True
        finally:
            _restore_root(old)


def test_missing_manifest_or_skill_ingest_rejected_fail_closed() -> None:
    te = importlib.import_module("core_brain.compiler.task_enforcer")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_runtime_boundary_audit())
        _write(root / "skills" / "runtime_boundary_audit" / "SKILL.md", _skill_md())
        old = _set_root(root)
        try:
            plan_missing_manifest = {
                "id": "rba1",
                "skill": "runtime_boundary_audit",
                "steps": [
                    {
                        "tool": "context_ingest",
                        "skill_id": "runtime_boundary_audit",
                        "path": "skills/runtime_boundary_audit/SKILL.md",
                    },
                    {"tool": "read_file", "params": {"path": "README.md"}},
                ],
                "execution_contract": {
                    "required_preamble": ["verify-first"],
                    "caps_profile": "read_assist_only",
                    "retry_policy": {"max_retries": 0, "single_flight": True, "no_parallel": True},
                },
            }
            p1 = root / "plan_missing_manifest.json"
            _write(p1, json.dumps(plan_missing_manifest))
            out1 = te.validate_plan_report(str(p1))
            assert out1["ok"] is False
            assert any("manifest_not_ingested" in s for s in out1["why_not"])

            plan_missing_skill = {
                "id": "rba2",
                "skill": "runtime_boundary_audit",
                "steps": [
                    {"tool": "context_ingest", "path": "skills/manifest.md"},
                    {"tool": "read_file", "params": {"path": "README.md"}},
                ],
                "execution_contract": {
                    "required_preamble": ["verify-first"],
                    "caps_profile": "read_assist_only",
                    "retry_policy": {"max_retries": 0, "single_flight": True, "no_parallel": True},
                },
            }
            p2 = root / "plan_missing_skill.json"
            _write(p2, json.dumps(plan_missing_skill))
            out2 = te.validate_plan_report(str(p2))
            assert out2["ok"] is False
            assert any("mandatory_read_missing" in s for s in out2["why_not"])
        finally:
            _restore_root(old)


def test_missing_execution_contract_rejected_fail_closed() -> None:
    te = importlib.import_module("core_brain.compiler.task_enforcer")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_runtime_boundary_audit())
        _write(root / "skills" / "runtime_boundary_audit" / "SKILL.md", _skill_md())
        old = _set_root(root)
        try:
            plan = {
                "id": "rba3",
                "skill": "runtime_boundary_audit",
                "steps": [
                    {"tool": "context_ingest", "path": "skills/manifest.md"},
                    {
                        "tool": "context_ingest",
                        "skill_id": "runtime_boundary_audit",
                        "path": "skills/runtime_boundary_audit/SKILL.md",
                    },
                    {"tool": "read_file", "params": {"path": "README.md"}},
                ],
            }
            p = root / "plan_missing_contract.json"
            _write(p, json.dumps(plan))
            out = te.validate_plan_report(str(p))
            assert out["ok"] is False
            assert any("execution_contract" in s for s in out["why_not"])
        finally:
            _restore_root(old)


def test_valid_ingest_and_contract_pass_and_emit_provenance() -> None:
    te = importlib.import_module("core_brain.compiler.task_enforcer")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_runtime_boundary_audit())
        _write(root / "skills" / "runtime_boundary_audit" / "SKILL.md", _skill_md())
        old = _set_root(root)
        try:
            plan = {
                "id": "rba4",
                "trace_id": "trace-rba4",
                "author": "tester",
                "skill": "runtime_boundary_audit",
                "steps": [
                    {"tool": "context_ingest", "path": "skills/manifest.md"},
                    {
                        "tool": "context_ingest",
                        "skill_id": "runtime_boundary_audit",
                        "path": "skills/runtime_boundary_audit/SKILL.md",
                    },
                    {"tool": "read_file", "params": {"path": "README.md"}},
                ],
                "execution_contract": {
                    "required_preamble": ["verify-first"],
                    "caps_profile": "read_assist_only",
                    "retry_policy": {"max_retries": 0, "single_flight": True, "no_parallel": True},
                },
            }
            p = root / "plan_pass.json"
            _write(p, json.dumps(plan))
            out = te.validate_plan_report(str(p))
            assert out["ok"] is True, out

            rows = _read_jsonl(root / "observability" / "artifacts" / "run_provenance.jsonl")
            assert any(r.get("tool") == "SkillIngestRunner" for r in rows)
        finally:
            _restore_root(old)


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    test_manifest_row_loads_without_wiring_error()
    test_missing_manifest_or_skill_ingest_rejected_fail_closed()
    test_missing_execution_contract_rejected_fail_closed()
    test_valid_ingest_and_contract_pass_and_emit_provenance()
    print("test_phase15_runtime_boundary_audit_wiring: all ok")
