#!/usr/bin/env python3
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.runtime.invariants.no_machine_paths import scan_repo_for_machine_paths
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


def test_runtime_boundary_audit_detects_machine_specific_path_read_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_runtime_boundary_audit())
        _write(root / "skills" / "runtime_boundary_audit" / "SKILL.md", _skill_md())
        suspect = root / "runtime" / "suspect.py"
        suspect_content = 'OPTION_REPO = Path("/Users/icmini/repos/option")\n'
        _write(suspect, suspect_content)
        old = _set_root(root)
        try:
            plan = {
                "id": "rba-domain-1",
                "trace_id": "trace-rba-domain-1",
                "author": "tester",
                "skill": "runtime_boundary_audit",
                "steps": [
                    {"tool": "context_ingest", "path": "skills/manifest.md"},
                    {
                        "tool": "context_ingest",
                        "skill_id": "runtime_boundary_audit",
                        "path": "skills/runtime_boundary_audit/SKILL.md",
                    },
                    {"tool": "read_file", "params": {"path": "runtime/suspect.py"}},
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

            before = suspect.read_text(encoding="utf-8")
            violations = scan_repo_for_machine_paths(root)
            after = suspect.read_text(encoding="utf-8")

            assert before == suspect_content
            assert after == suspect_content
            assert violations == [
                'runtime/suspect.py:1:OPTION_REPO = Path("/Users/icmini/repos/option")'
            ]
        finally:
            _restore_root(old)


if __name__ == "__main__":
    test_runtime_boundary_audit_detects_machine_specific_path_read_only()
    print("test_phase15_runtime_boundary_audit_minimal_domain: all ok")
