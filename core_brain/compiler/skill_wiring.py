#!/usr/bin/env python3
"""Phase 15.4: Deterministic Skill OS wiring + alias resolution."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

import yaml

from core.run_provenance import append_provenance, complete_run_provenance, init_run_provenance


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


def _resolve_root() -> Path:
    raw = os.environ.get("ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve(strict=False)
    return Path(__file__).resolve().parents[2]


def _aliases_path() -> Path:
    return _resolve_root() / "skills" / "aliases" / "aliases_v1.yaml"


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


def _normalize_skill_id(skill_id: str) -> str:
    return skill_id.strip().casefold().replace("_", "-")


def _parse_manifest_skill_ids(manifest_path: Path) -> Set[str]:
    skill_ids: Set[str] = set()
    if not manifest_path.exists():
        return skill_ids
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if "|" not in line or "`" not in line:
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 1:
            continue
        skill_cell = cells[0]
        if not (skill_cell.startswith("`") and skill_cell.endswith("`")):
            continue
        skill_id = skill_cell[1:-1].strip()
        if skill_id:
            skill_ids.add(skill_id)
    return skill_ids


def _load_aliases() -> Dict[str, List[str]]:
    path = _aliases_path()
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SkillWiringError(f"alias_map_invalid_yaml:{exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SkillWiringError("alias_map_invalid_root")
    aliases_raw = data.get("aliases", {})
    if not isinstance(aliases_raw, dict):
        raise SkillWiringError("alias_map_invalid_aliases")
    aliases: Dict[str, List[str]] = {}
    for key, value in aliases_raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise SkillWiringError("alias_map_invalid_entry_type")
        nk = _normalize_skill_id(key)
        nv = value.strip()
        if not nk or not nv:
            raise SkillWiringError("alias_map_invalid_entry")
        aliases.setdefault(nk, [])
        if nv not in aliases[nk]:
            aliases[nk].append(nv)
    return aliases


def _emit_alias_resolution_provenance(requested_id: str, resolved_id: str) -> None:
    aliases_path = _aliases_path()
    manifest_path = _resolve_root() / "skills" / "manifest.md"
    execution_input = {
        "phase": "phase15.4",
        "event": "skill_alias_resolution",
        "requested_id": requested_id,
        "resolved_id": resolved_id,
        "aliases_path": str(aliases_path),
    }
    base = {
        "author": "skill_wiring",
        "tool": "SkillAliasResolver",
        "evidence_refs": [f"file:{aliases_path}", f"file:{manifest_path}"],
    }
    row = init_run_provenance(base, execution_input)
    row = complete_run_provenance(
        row,
        {"status": "resolved", "requested_id": requested_id, "resolved_id": resolved_id},
    )
    row["requested_id"] = requested_id
    row["resolved_id"] = resolved_id
    append_provenance(row)


def _encode_unknown_error(requested_id: str, normalized_id: str, attempted_aliases: List[str]) -> str:
    return (
        "skill_mapping_missing:"
        f"requested_id={requested_id};"
        f"normalized_id={normalized_id};"
        f"attempted_aliases={','.join(attempted_aliases)};"
        "hint=list available skills"
    )


def resolve_selected_skills(
    selected_skills: Iterable[str], wiring_map: Dict[str, SkillWiringRow]
) -> Tuple[List[str], List[Tuple[str, str]]]:
    selected_raw = sorted({s.strip() for s in selected_skills if isinstance(s, str) and s.strip()})
    if not selected_raw:
        return ([], [])

    aliases = _load_aliases()
    manifest_skill_ids = _parse_manifest_skill_ids(_resolve_root() / "skills" / "manifest.md")

    resolved: List[str] = []
    alias_events: List[Tuple[str, str]] = []
    unknown_errors: List[str] = []

    for requested in selected_raw:
        if requested in wiring_map:
            resolved.append(requested)
            continue

        normalized = _normalize_skill_id(requested)
        candidates = aliases.get(normalized, [])
        if candidates:
            missing = [candidate for candidate in candidates if candidate not in manifest_skill_ids]
            if missing:
                raise SkillWiringError(
                    "skill_alias_invalid_target:"
                    f"requested_id={requested};normalized_id={normalized};"
                    f"attempted_aliases={','.join(candidates)};hint=list available skills"
                )
            if len(candidates) > 1:
                raise SkillWiringError(
                    "skill_alias_ambiguous:"
                    f"requested_id={requested};normalized_id={normalized};"
                    f"attempted_aliases={','.join(candidates)};hint=list available skills"
                )
            candidate = candidates[0]
            if candidate in wiring_map:
                resolved.append(candidate)
                alias_events.append((requested, candidate))
                continue

        unknown_errors.append(_encode_unknown_error(requested, normalized, candidates))

    if unknown_errors:
        raise SkillWiringError("|".join(unknown_errors))

    return (sorted(set(resolved)), alias_events)


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
    selected, alias_events = resolve_selected_skills(selected_skills, wiring_map)
    if not selected:
        return {
            "required_preamble": [],
            "caps_profile": "",
            "retry_policy": {"max_retries": 0, "single_flight": True, "no_parallel": True},
        }

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

    for requested_id, resolved_id in alias_events:
        _emit_alias_resolution_provenance(requested_id, resolved_id)

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
