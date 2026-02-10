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
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _prepare_root(tmp_root: Path) -> None:
    _write(
        tmp_root / "skills" / "manifest.md",
        """# skill manifest\n\n"
        "| skill_id | purpose | Mandatory Read | MCPs used | Inputs | Outputs | Caps | Forbidden actions |\n"
        "| :--- | :--- | :---: | :--- | :--- | :--- | :--- | :--- |\n"
        "| `knowledge_recycling` | test | YES | fs | in | out | cap | forbid |\n"
        """,
    )
    _write(
        tmp_root / "skills" / "knowledge_recycling" / "SKILL.md",
        "# Skill\n\nMandatory Read: YES\n",
    )


def _with_root(root: Path):
    previous = os.environ.get("ROOT")
    os.environ["ROOT"] = str(root)
    return previous


def _restore_root(previous):
    if previous is None:
        os.environ.pop("ROOT", None)
    else:
        os.environ["ROOT"] = previous


def test_reject_missing_manifest_or_mandatory_ingest() -> None:
    te = importlib.import_module("core_brain.compiler.task_enforcer")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _prepare_root(root)
        previous = _with_root(root)

        plan = {
            "id": "t1",
            "trace_id": "trace-t1",
            "skill": "knowledge_recycling",
            "steps": [
                {"tool": "read_file", "params": {"path": "README.md"}},
            ],
        }
        plan_path = root / "plan_missing.json"
        _write(plan_path, json.dumps(plan))

        try:
            report = te.validate_plan_report(str(plan_path))
            assert report["ok"] is False
            why = "\n".join(report["why_not"])
            assert "manifest" in why.lower() or "mandatory_read" in why.lower()
        finally:
            _restore_root(previous)


def test_pass_when_manifest_and_mandatory_ingest_present() -> None:
    te = importlib.import_module("core_brain.compiler.task_enforcer")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _prepare_root(root)
        previous = _with_root(root)

        plan = {
            "id": "t2",
            "trace_id": "trace-t2",
            "author": "tester",
            "skill": "knowledge_recycling",
            "steps": [
                {"tool": "context_ingest", "path": "skills/manifest.md"},
                {
                    "tool": "context_ingest",
                    "skill_id": "knowledge_recycling",
                    "path": "skills/knowledge_recycling/SKILL.md",
                },
                {"tool": "read_file", "params": {"path": "README.md"}},
            ],
        }
        plan_path = root / "plan_pass.json"
        _write(plan_path, json.dumps(plan))

        try:
            report = te.validate_plan_report(str(plan_path))
            assert report["ok"] is True
            assert report["why_not"] == []
        finally:
            _restore_root(previous)


def test_ingest_emits_skill_ingestrunner_provenance() -> None:
    te = importlib.import_module("core_brain.compiler.task_enforcer")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _prepare_root(root)
        previous = _with_root(root)

        plan = {
            "id": "t3",
            "trace_id": "trace-t3",
            "author": "tester",
            "skill": "knowledge_recycling",
            "steps": [
                {"tool": "context_ingest", "path": "skills/manifest.md"},
                {
                    "tool": "context_ingest",
                    "skill_id": "knowledge_recycling",
                    "path": "skills/knowledge_recycling/SKILL.md",
                },
                {"tool": "read_file", "params": {"path": "README.md"}},
            ],
        }
        plan_path = root / "plan_prov.json"
        _write(plan_path, json.dumps(plan))

        try:
            report = te.validate_plan_report(str(plan_path))
            assert report["ok"] is True

            rows = _read_jsonl(root / "observability" / "artifacts" / "run_provenance.jsonl")
            assert rows, "missing_provenance_rows"
            assert any(r.get("tool") == "SkillIngestRunner" for r in rows)
            hit = next(r for r in rows if r.get("tool") == "SkillIngestRunner")
            assert hit.get("author") == "tester"
            assert hit.get("input_hash")
            assert hit.get("output_hash")
        finally:
            _restore_root(previous)


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    test_reject_missing_manifest_or_mandatory_ingest()
    test_pass_when_manifest_and_mandatory_ingest_present()
    test_ingest_emits_skill_ingestrunner_provenance()
    print("test_phase15_1_skill_wiring: all ok")
