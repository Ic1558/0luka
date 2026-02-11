#!/usr/bin/env python3
"""
Task Enforcer: Validates agent plans against Sovereign Rules.
Enforces:
1. Manifest Lock (Must read manifest)
2. Mandatory Read Interlock (Must read flagged skills)
Returns exit code 0 if compliant, 1 if violation.
"""
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set

from core.run_provenance import append_provenance, complete_run_provenance, init_run_provenance
from core_brain.compiler.skill_wiring import (
    SkillWiringError,
    load_wiring_map,
    resolve_selected_skills,
    resolve_execution_contract,
    validate_execution_contract,
)

ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_root() -> Path:
    raw = os.environ.get("ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve(strict=False)
    return ROOT


def _manifest_path() -> Path:
    return _resolve_root() / "skills" / "manifest.md"


def _skills_dir() -> Path:
    return _resolve_root() / "skills"


def _parse_manifest_mandatory(manifest_path: Path) -> Set[str]:
    mandatory: Set[str] = set()
    if not manifest_path.exists():
        return mandatory

    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if "|" not in line or "`" not in line:
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 3:
            continue
        skill_cell = cells[0]
        mandatory_cell = cells[2].upper()
        if not (skill_cell.startswith("`") and skill_cell.endswith("`")):
            continue
        skill_id = skill_cell[1:-1].strip()
        if not skill_id:
            continue
        if mandatory_cell == "YES":
            mandatory.add(skill_id)
    return mandatory


def load_manifest_rules() -> Set[str]:
    """Load mandatory-read skills from manifest and SKILL fallback."""
    mandatory_skills = _parse_manifest_mandatory(_manifest_path())
    skills_dir = _skills_dir()
    if not skills_dir.exists():
        return mandatory_skills

    for skill_file in skills_dir.glob("**/SKILL.md"):
        try:
            content = skill_file.read_text(encoding="utf-8")
            if "Mandatory Read: YES" in content:
                mandatory_skills.add(skill_file.parent.name)
        except Exception:
            continue
    return mandatory_skills


def _selected_skills(plan: Dict[str, object], steps: List[Dict[str, object]]) -> Set[str]:
    selected: Set[str] = set()
    for key in ("skill", "skill_id"):
        value = plan.get(key)
        if isinstance(value, str) and value.strip():
            selected.add(value.strip())

    skills = plan.get("skills")
    if isinstance(skills, list):
        for item in skills:
            if isinstance(item, str) and item.strip():
                selected.add(item.strip())

    for step in steps:
        sid = step.get("skill_id")
        if isinstance(sid, str) and sid.strip():
            selected.add(sid.strip())
    return selected


def _extract_ingest_paths(step: Dict[str, object]) -> List[str]:
    paths: List[str] = []
    for key in ("path", "target", "target_path", "file", "input", "ref"):
        val = step.get(key)
        if isinstance(val, str):
            paths.append(val)

    params = step.get("params")
    if isinstance(params, dict):
        for key in ("path", "target", "target_path", "file", "input", "ref"):
            val = params.get(key)
            if isinstance(val, str):
                paths.append(val)
    return paths


def _collect_context_ingest(steps: List[Dict[str, object]]) -> Dict[str, List[str]]:
    ingested: Dict[str, List[str]] = {}
    for step in steps:
        tool = step.get("tool")
        op = step.get("op")
        action = step.get("action")
        if tool != "context_ingest" and op != "context_ingest" and action != "context_ingest":
            continue

        skill_id = step.get("skill_id")
        if isinstance(skill_id, str) and skill_id.strip():
            ingested.setdefault(skill_id.strip(), [])

        for path in _extract_ingest_paths(step):
            normalized = path.strip()
            if not normalized:
                continue
            if "skills/manifest.md" in normalized:
                ingested.setdefault("__manifest__", []).append(normalized)
            if "skills/" in normalized and normalized.endswith("/SKILL.md"):
                parts = normalized.split("skills/", 1)[1].split("/", 1)
                if parts and parts[0]:
                    ingested.setdefault(parts[0], []).append(normalized)
    return ingested


def _emit_skill_ingest_provenance(plan: Dict[str, object], skill_id: str, manifest_path: Path, skill_path: Path) -> None:
    trace_id = str(plan.get("trace_id") or plan.get("id") or "unknown")
    execution_input = {
        "phase": "phase15.1",
        "event": "skill_context_ingest",
        "trace_id": trace_id,
        "skill_id": skill_id,
        "manifest_path": str(manifest_path),
        "skill_md_path": str(skill_path),
    }
    base = {
        "author": str(plan.get("author") or "task_enforcer"),
        "tool": "SkillIngestRunner",
        "evidence_refs": [f"file:{manifest_path}", f"file:{skill_path}"],
    }
    row = init_run_provenance(base, execution_input)
    row = complete_run_provenance(row, {"status": "ingested", "trace_id": trace_id, "skill_id": skill_id})
    append_provenance(row)


def validate_plan_report(plan_json_path: str) -> Dict[str, object]:
    report: Dict[str, object] = {"ok": False, "why_not": []}
    try:
        with open(plan_json_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except Exception as exc:
        report["why_not"] = [f"plan_read_error:{exc}"]
        return report

    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        report["why_not"] = ["invalid_steps"]
        return report
    step_dicts = [s for s in steps if isinstance(s, dict)]

    manifest_path = _manifest_path()
    skills_dir = _skills_dir()
    why_not: List[str] = []

    if not manifest_path.exists():
        why_not.append(f"manifest_missing:{manifest_path}")

    mandatory_skills = load_manifest_rules()
    selected = _selected_skills(plan, step_dicts)
    ingested = _collect_context_ingest(step_dicts)
    selected_for_mandatory = set(selected)
    try:
        wiring_map = load_wiring_map(manifest_path)
        resolved_selected, _alias_events = resolve_selected_skills(selected, wiring_map)
        selected_for_mandatory = set(resolved_selected)
        expected_contract = resolve_execution_contract(selected, wiring_map)
    except SkillWiringError as exc:
        report["ok"] = False
        report["why_not"] = [f"skill_wiring_invalid:{exc}"]
        return report

    has_execution_steps = any((step.get("tool") or "") != "context_ingest" for step in step_dicts)
    if has_execution_steps and not ingested.get("__manifest__"):
        why_not.append(f"manifest_not_ingested:{manifest_path}")

    for skill_id in sorted(selected_for_mandatory):
        skill_path = skills_dir / skill_id / "SKILL.md"
        if skill_id in mandatory_skills and not ingested.get(skill_id):
            why_not.append(f"mandatory_read_missing:{skill_path}")

    why_not.extend(validate_execution_contract(plan.get("execution_contract"), expected_contract))

    if why_not:
        report["ok"] = False
        report["why_not"] = why_not
        return report

    for skill_id in sorted(selected_for_mandatory):
        if not ingested.get(skill_id):
            continue
        skill_path = skills_dir / skill_id / "SKILL.md"
        _emit_skill_ingest_provenance(plan, skill_id, manifest_path, skill_path)

    report["ok"] = True
    report["why_not"] = []
    return report


def validate_plan(plan_json_path: str) -> bool:
    return bool(validate_plan_report(plan_json_path).get("ok"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: task_enforcer.py <plan.json>")
        sys.exit(1)

    result = validate_plan_report(sys.argv[1])
    if result.get("ok"):
        print("Plan Compliant.")
        sys.exit(0)

    for reason in result.get("why_not", []):
        print(f"why_not: {reason}")
    print("Plan Violation.")
    sys.exit(1)
