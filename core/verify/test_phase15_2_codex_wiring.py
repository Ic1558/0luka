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


def _manifest_with_wiring() -> str:
    return """# manifest

## Core-Brain Owned Skills (Phase 15)
| skill_id | purpose | Mandatory Read | MCPs used | Inputs | Outputs | Caps | Forbidden actions |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| `scope-lock` | lock scope | YES | fs | in | out | cap | forbid |

## Codex Hand Wiring Map (Phase 15.2)
| skill_id | required_preamble | caps_profile | max_retries | single_flight | no_parallel |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `scope-lock` | `scope-lock` | `read_assist_only` | 0 | true | true |
"""


def test_missing_execution_contract_rejected_fail_closed() -> None:
    te = importlib.import_module("core_brain.compiler.task_enforcer")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_wiring())
        _write(root / "skills" / "scope-lock" / "SKILL.md", "Mandatory Read: YES\n")
        old = _set_root(root)
        try:
            plan = {
                "id": "w1",
                "skill": "scope-lock",
                "steps": [
                    {"tool": "context_ingest", "path": "skills/manifest.md"},
                    {"tool": "context_ingest", "skill_id": "scope-lock", "path": "skills/scope-lock/SKILL.md"},
                    {"tool": "read_file", "params": {"path": "README.md"}},
                ],
            }
            p = root / "plan.json"
            _write(p, json.dumps(plan))
            out = te.validate_plan_report(str(p))
            assert out["ok"] is False
            why = "\n".join(out["why_not"])
            assert "execution_contract" in why
        finally:
            _restore_root(old)


def test_invalid_manifest_wiring_rejected_fail_closed() -> None:
    te = importlib.import_module("core_brain.compiler.task_enforcer")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", "# manifest without wiring\n")
        _write(root / "skills" / "scope-lock" / "SKILL.md", "Mandatory Read: YES\n")
        old = _set_root(root)
        try:
            plan = {
                "id": "w2",
                "skill": "scope-lock",
                "steps": [{"tool": "read_file", "params": {"path": "README.md"}}],
                "execution_contract": {
                    "required_preamble": ["scope-lock"],
                    "caps_profile": "read_assist_only",
                    "retry_policy": {"max_retries": 0, "single_flight": True, "no_parallel": True},
                },
            }
            p = root / "plan.json"
            _write(p, json.dumps(plan))
            out = te.validate_plan_report(str(p))
            assert out["ok"] is False
            assert any("skill_wiring_invalid" in s for s in out["why_not"])
        finally:
            _restore_root(old)


def test_mandatory_skill_with_ingest_and_contract_emits_provenance() -> None:
    te = importlib.import_module("core_brain.compiler.task_enforcer")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_wiring())
        _write(root / "skills" / "scope-lock" / "SKILL.md", "Mandatory Read: YES\n")
        old = _set_root(root)
        try:
            plan = {
                "id": "w3",
                "trace_id": "trace-w3",
                "author": "tester",
                "skill": "scope-lock",
                "steps": [
                    {"tool": "context_ingest", "path": "skills/manifest.md"},
                    {"tool": "context_ingest", "skill_id": "scope-lock", "path": "skills/scope-lock/SKILL.md"},
                    {"tool": "read_file", "params": {"path": "README.md"}},
                ],
                "execution_contract": {
                    "required_preamble": ["scope-lock"],
                    "caps_profile": "read_assist_only",
                    "retry_policy": {"max_retries": 0, "single_flight": True, "no_parallel": True},
                },
            }
            p = root / "plan.json"
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
    test_missing_execution_contract_rejected_fail_closed()
    test_invalid_manifest_wiring_rejected_fail_closed()
    test_mandatory_skill_with_ingest_and_contract_emits_provenance()
    print("test_phase15_2_codex_wiring: all ok")
