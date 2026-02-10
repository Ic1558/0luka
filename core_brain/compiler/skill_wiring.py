#!/usr/bin/env python3
"""Phase 15.2: Deterministic Skill OS wiring from skills/manifest.md."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set


class SkillWiringError(RuntimeError):
    pass


@dataclass(frozen=True)
class SkillWiringRow:
    skill_id: str
    required_preamble: str
    caps_profile: str
    max_retries: int
    single_flight: bool
    no_parallel: bool


def _strip_ticks(value: str) -> str:
    v = value.strip()
    if v.startswith("`") and v.endswith("`") and len(v) >= 2:
        return v[1:-1].strip()
    return v


def _to_bool(value: str) -> bool:
    v = value.strip().lower()
    if v == "true":
        return True
    if v == "false":
        return False
    raise SkillWiringError(f"invalid_bool:{value}")


def load_wiring_map(manifest_path: Path) -> Dict[str, SkillWiringRow]:
    if not manifest_path.exists():
        raise SkillWiringError(f"manifest_missing:{manifest_path}")

    text = manifest_path.read_text(encoding="utf-8")
    if "## Codex Hand Wiring Map (Phase 15.2)" not in text:
        raise SkillWiringError("wiring_section_missing")

    in_table = False
    rows: Dict[str, SkillWiringRow] = {}
    for line in text.splitlines():
        if line.strip() == "## Codex Hand Wiring Map (Phase 15.2)":
            in_table = True
            continue
        if not in_table:
            continue
        if in_table and line.startswith("## "):
            break
        if "|" not in line or "`" not in line:
            continue

        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) != 6:
            continue
        if cells[0] == "skill_id" or cells[0].startswith(":---"):
            continue

        skill_cell = cells[0]
        preamble_cell = cells[1]
        if not (skill_cell.startswith("`") and skill_cell.endswith("`")):
            continue
        if not (preamble_cell.startswith("`") and preamble_cell.endswith("`")):
            raise SkillWiringError(f"invalid_required_preamble:{preamble_cell}")

        skill_id = skill_cell[1:-1].strip()
        if not skill_id:
            raise SkillWiringError("invalid_skill_id")
        if skill_id in rows:
            raise SkillWiringError(f"duplicate_skill_mapping:{skill_id}")

        try:
            max_retries = int(cells[3])
        except ValueError as exc:
            raise SkillWiringError(f"invalid_max_retries:{cells[3]}") from exc

        rows[skill_id] = SkillWiringRow(
            skill_id=skill_id,
            required_preamble=preamble_cell[1:-1].strip(),
            caps_profile=_strip_ticks(cells[2]),
            max_retries=max_retries,
            single_flight=_to_bool(cells[4]),
            no_parallel=_to_bool(cells[5]),
        )

    if not rows:
        raise SkillWiringError("wiring_rows_missing")
    return rows


def resolve_execution_contract(selected_skills: Iterable[str], wiring_map: Dict[str, SkillWiringRow]) -> Dict[str, object]:
    selected = sorted({s.strip() for s in selected_skills if isinstance(s, str) and s.strip()})
    if not selected:
        return {
            "required_preamble": [],
            "caps_profile": "",
            "retry_policy": {"max_retries": 0, "single_flight": True, "no_parallel": True},
        }

    missing = [s for s in selected if s not in wiring_map]
    if missing:
        raise SkillWiringError(f"skill_mapping_missing:{','.join(missing)}")

    rows = [wiring_map[s] for s in selected]
    caps_profiles = {r.caps_profile for r in rows}
    if len(caps_profiles) != 1:
        raise SkillWiringError("caps_profile_conflict")

    max_retries_values = {r.max_retries for r in rows}
    single_flight_values = {r.single_flight for r in rows}
    no_parallel_values = {r.no_parallel for r in rows}

    if len(max_retries_values) != 1:
        raise SkillWiringError("max_retries_conflict")
    if len(single_flight_values) != 1:
        raise SkillWiringError("single_flight_conflict")
    if len(no_parallel_values) != 1:
        raise SkillWiringError("no_parallel_conflict")

    return {
        "required_preamble": sorted({r.required_preamble for r in rows}),
        "caps_profile": next(iter(caps_profiles)),
        "retry_policy": {
            "max_retries": next(iter(max_retries_values)),
            "single_flight": next(iter(single_flight_values)),
            "no_parallel": next(iter(no_parallel_values)),
        },
    }


def validate_execution_contract(plan_contract: object, required_contract: Dict[str, object]) -> List[str]:
    why_not: List[str] = []
    if not isinstance(plan_contract, dict):
        return ["execution_contract_missing"]

    required_preamble = required_contract.get("required_preamble")
    if not isinstance(required_preamble, list):
        return ["required_contract_invalid_preamble"]
    provided_preamble = plan_contract.get("required_preamble")
    if not isinstance(provided_preamble, list):
        why_not.append("execution_contract_missing_required_preamble")
    else:
        for item in required_preamble:
            if item not in provided_preamble:
                why_not.append(f"execution_contract_missing_preamble:{item}")

    expected_caps = required_contract.get("caps_profile")
    if plan_contract.get("caps_profile") != expected_caps:
        why_not.append(f"execution_contract_caps_profile_mismatch:{expected_caps}")

    expected_retry = required_contract.get("retry_policy")
    provided_retry = plan_contract.get("retry_policy")
    if not isinstance(expected_retry, dict):
        return ["required_contract_invalid_retry_policy"]
    if not isinstance(provided_retry, dict):
        why_not.append("execution_contract_missing_retry_policy")
    else:
        for key in ("max_retries", "single_flight", "no_parallel"):
            if provided_retry.get(key) != expected_retry.get(key):
                why_not.append(f"execution_contract_retry_policy_mismatch:{key}")
    return why_not
