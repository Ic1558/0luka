#!/usr/bin/env python3
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core_brain.compiler.task_enforcer import validate_plan_report


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _run_fail_closed_ambiguous_evidence(root: Path, relative_glob: str) -> dict:
    matches = sorted(
        p.relative_to(root).as_posix()
        for p in root.glob(relative_glob)
        if p.is_file()
    )
    if len(matches) != 1:
        return {
            "ok": False,
            "status": "fail_closed",
            "reason": f"ambiguous_boundary_evidence:{relative_glob}",
            "matches": matches,
        }
    return {"ok": True, "status": "ok", "reason": "", "matches": matches}


def test_runtime_boundary_audit_ambiguous_runtime_evidence_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_runtime_boundary_audit())
        _write(root / "skills" / "runtime_boundary_audit" / "SKILL.md", _skill_md())
        _write(root / "runtime" / "candidate_a.py", "VALUE = 'a'\\n")
        _write(root / "runtime" / "candidate_b.py", "VALUE = 'b'\\n")
        old = _set_root(root)
        try:
            relative_glob = "runtime/candidate_*.py"
            plan = {
                "id": "rba-domain-4",
                "trace_id": "trace-rba-domain-4",
                "author": "tester",
                "skill": "runtime_boundary_audit",
                "steps": [
                    {"tool": "context_ingest", "path": "skills/manifest.md"},
                    {
                        "tool": "context_ingest",
                        "skill_id": "runtime_boundary_audit",
                        "path": "skills/runtime_boundary_audit/SKILL.md",
                    },
                    {"tool": "read_file", "params": {"path": relative_glob}},
                ],
                "execution_contract": {
                    "required_preamble": ["verify-first"],
                    "caps_profile": "read_assist_only",
                    "retry_policy": {"max_retries": 0, "single_flight": True, "no_parallel": True},
                },
            }
            plan_path = root / "plan.json"
            _write(plan_path, json.dumps(plan))
            out = validate_plan_report(str(plan_path))
            assert out["ok"] is True, out

            result = _run_fail_closed_ambiguous_evidence(root, relative_glob)
            assert result == {
                "ok": False,
                "status": "fail_closed",
                "reason": "ambiguous_boundary_evidence:runtime/candidate_*.py",
                "matches": ["runtime/candidate_a.py", "runtime/candidate_b.py"],
            }
        finally:
            _restore_root(old)


if __name__ == "__main__":
    test_runtime_boundary_audit_ambiguous_runtime_evidence_fails_closed()
    print("test_phase15_runtime_boundary_audit_ambiguous_domain: all ok")
