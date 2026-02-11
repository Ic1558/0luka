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
| `verify-first` | verify discipline | YES | fs | in | out | cap | forbid |

## Codex Hand Wiring Map (Phase 15.2)
| skill_id | required_preamble | caps_profile | max_retries | single_flight | no_parallel |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `verify-first` | `verify-first` | `read_assist_only` | 0 | true | true |
"""


def _alias_map() -> str:
    return """schema_version: "skill_aliases_v1"
normalize:
  casefold: true
  treat_underscore_as_dash: true
aliases:
  extra-usage: verify-first
  extra_usage: verify-first
"""


def test_extra_usage_alias_resolves() -> None:
    sw = importlib.import_module("core_brain.compiler.skill_wiring")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_wiring())
        _write(root / "skills" / "aliases" / "aliases_v1.yaml", _alias_map())
        old = _set_root(root)
        try:
            wiring = sw.load_wiring_map(root / "skills" / "manifest.md")
            out = sw.resolve_execution_contract(["extra-usage"], wiring)
            assert out["required_preamble"] == ["verify-first"]
        finally:
            _restore_root(old)


def test_alias_normalization_variants_resolve() -> None:
    sw = importlib.import_module("core_brain.compiler.skill_wiring")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_wiring())
        _write(root / "skills" / "aliases" / "aliases_v1.yaml", _alias_map())
        old = _set_root(root)
        try:
            wiring = sw.load_wiring_map(root / "skills" / "manifest.md")
            out = sw.resolve_execution_contract(["EXTRA-USAGE", "extra_usage"], wiring)
            assert out["required_preamble"] == ["verify-first"]
            assert out["caps_profile"] == "read_assist_only"
        finally:
            _restore_root(old)


def test_unknown_skill_error_contains_required_fields() -> None:
    sw = importlib.import_module("core_brain.compiler.skill_wiring")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_wiring())
        _write(root / "skills" / "aliases" / "aliases_v1.yaml", _alias_map())
        old = _set_root(root)
        try:
            wiring = sw.load_wiring_map(root / "skills" / "manifest.md")
            try:
                sw.resolve_execution_contract(["totally_unknown_skill"], wiring)
            except sw.SkillWiringError as exc:
                msg = str(exc)
                assert "skill_mapping_missing:" in msg
                assert "requested_id" in msg
                assert "normalized_id" in msg
                assert "attempted_aliases" in msg
                assert "list available skills" in msg
            else:
                raise AssertionError("expected SkillWiringError")
        finally:
            _restore_root(old)


def test_ambiguous_alias_rejected_deterministically() -> None:
    sw = importlib.import_module("core_brain.compiler.skill_wiring")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_wiring().replace(
            "| `verify-first` | verify discipline | YES | fs | in | out | cap | forbid |\n",
            "| `verify-first` | verify discipline | YES | fs | in | out | cap | forbid |\n"
            "| `scope-lock` | scope discipline | YES | fs | in | out | cap | forbid |\n",
        ).replace(
            "| `verify-first` | `verify-first` | `read_assist_only` | 0 | true | true |\n",
            "| `verify-first` | `verify-first` | `read_assist_only` | 0 | true | true |\n"
            "| `scope-lock` | `scope-lock` | `read_assist_only` | 0 | true | true |\n",
        ))
        _write(
            root / "skills" / "aliases" / "aliases_v1.yaml",
            """schema_version: "skill_aliases_v1"
normalize:
  casefold: true
  treat_underscore_as_dash: true
aliases:
  extra-usage: verify-first
  extra_usage: scope-lock
""",
        )
        old = _set_root(root)
        try:
            wiring = sw.load_wiring_map(root / "skills" / "manifest.md")
            try:
                sw.resolve_execution_contract(["extra-usage"], wiring)
            except sw.SkillWiringError as exc:
                msg = str(exc)
                assert "skill_alias_ambiguous:" in msg
                assert "requested_id=extra-usage" in msg
                assert "attempted_aliases=verify-first,scope-lock" in msg
            else:
                raise AssertionError("expected SkillWiringError")
        finally:
            _restore_root(old)


def test_alias_resolution_emits_provenance_row() -> None:
    sw = importlib.import_module("core_brain.compiler.skill_wiring")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_wiring())
        _write(root / "skills" / "aliases" / "aliases_v1.yaml", _alias_map())
        old = _set_root(root)
        try:
            wiring = sw.load_wiring_map(root / "skills" / "manifest.md")
            sw.resolve_execution_contract(["extra-usage"], wiring)
            rows = _read_jsonl(root / "observability" / "artifacts" / "run_provenance.jsonl")
            hit = None
            for row in rows:
                if row.get("tool") == "SkillAliasResolver":
                    hit = row
                    break
            assert hit is not None, rows
            assert hit.get("requested_id") == "extra-usage"
            assert hit.get("resolved_id") == "verify-first"
        finally:
            _restore_root(old)


def test_alias_preserves_mandatory_ingest_interlock() -> None:
    te = importlib.import_module("core_brain.compiler.task_enforcer")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "skills" / "manifest.md", _manifest_with_wiring())
        _write(root / "skills" / "aliases" / "aliases_v1.yaml", _alias_map())
        _write(root / "skills" / "verify-first" / "SKILL.md", "Mandatory Read: YES\n")
        old = _set_root(root)
        try:
            plan = {
                "id": "alias-m1",
                "skill": "extra-usage",
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
            p = root / "plan.json"
            _write(p, json.dumps(plan))
            out = te.validate_plan_report(str(p))
            assert out["ok"] is False
            why = "\n".join(out["why_not"])
            assert "mandatory_read_missing" in why
            assert "skills/verify-first/SKILL.md" in why
        finally:
            _restore_root(old)


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    test_extra_usage_alias_resolves()
    test_alias_normalization_variants_resolve()
    test_unknown_skill_error_contains_required_fields()
    test_ambiguous_alias_rejected_deterministically()
    test_alias_resolution_emits_provenance_row()
    test_alias_preserves_mandatory_ingest_interlock()
    print("test_phase15_4_skill_aliases: all ok")
