"""
skill_loader.py — Load and validate skill families from the skills/ directory.
"""

import importlib.util
import json
import sys
from pathlib import Path

from core.skill_contract import validate_manifest, validate_handler

SKILLS_DIR = Path(__file__).parent.parent / "skills"

_SKILL_FAMILIES = ["file_ops", "git_ops", "system_ops", "analysis", "trading"]


class SkillLoadError(Exception):
    """Raised when a skill cannot be loaded or fails validation."""
    pass


def load_skill(family: str) -> dict:
    """
    Load a single skill family.
    Returns {"manifest": dict, "handler": module}.
    Raises SkillLoadError on validation failure.
    """
    skill_dir = SKILLS_DIR / family

    if not skill_dir.exists():
        raise SkillLoadError(f"skill directory not found: {skill_dir}")

    # Load manifest
    manifest_path = skill_dir / "skill.json"
    if not manifest_path.exists():
        raise SkillLoadError(f"skill.json not found for family '{family}': {manifest_path}")

    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        raise SkillLoadError(f"skill.json parse error for family '{family}': {e}")

    valid, reason = validate_manifest(manifest)
    if not valid:
        raise SkillLoadError(f"manifest validation failed for family '{family}': {reason}")

    # Load handler
    handler_path = skill_dir / "handler.py"
    if not handler_path.exists():
        raise SkillLoadError(f"handler.py not found for family '{family}': {handler_path}")

    module_name = f"skills.{family}.handler"
    spec = importlib.util.spec_from_file_location(module_name, handler_path)
    handler = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = handler
    try:
        spec.loader.exec_module(handler)
    except Exception as e:
        raise SkillLoadError(f"handler.py load error for family '{family}': {e}")

    valid, reason = validate_handler(handler)
    if not valid:
        raise SkillLoadError(f"handler validation failed for family '{family}': {reason}")

    return {"manifest": manifest, "handler": handler}


def load_all_skills() -> dict:
    """
    Load all 5 skill families.
    Returns {family: {"manifest": dict, "handler": module}}.
    Raises SkillLoadError if any family fails.
    """
    result = {}
    for family in _SKILL_FAMILIES:
        result[family] = load_skill(family)
    return result
