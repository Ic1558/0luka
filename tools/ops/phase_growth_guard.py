#!/usr/bin/env python3
"""
Phase/Module Growth Guard

Step 3 goals:
- Enforce deterministic phase naming and placement.
- Prevent new phase creation without required scaffold.
- Provide CI-friendly and local preflight validation.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

import yaml


PHASE_RE = re.compile(r"^PHASE_[A-Z0-9_]+$")
MODULE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
DEFAULT_REGISTRY = "core/governance/phase_status.yaml"


@dataclass(frozen=True)
class PhaseCheckResult:
    phase_id: str
    ok: bool
    errors: List[str]
    expected_paths: Dict[str, str]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def normalize_phase_id(phase_id: str) -> str:
    return phase_id.strip().upper()


def phase_slug(phase_id: str) -> str:
    return normalize_phase_id(phase_id).lower()


def expected_phase_paths(phase_id: str) -> Dict[str, str]:
    pid = normalize_phase_id(phase_id)
    slug = phase_slug(pid)
    return {
        "dod": f"docs/dod/DOD__{pid}.md",
        "registry": DEFAULT_REGISTRY,
        "test_stub": f"core/verify/test_{slug}.py",
        "proof_harness": f"core/verify/prove_{slug}.py",
    }


def load_registry_phase_ids(registry_path: Path) -> Set[str]:
    if not registry_path.exists():
        return set()
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    phases = payload.get("phases", {})
    if not isinstance(phases, dict):
        return set()
    return {str(k).strip().upper() for k in phases.keys() if str(k).strip()}


def _diff_name_status(root: Path, base: str, head: str) -> List[Tuple[str, List[str]]]:
    out = subprocess.check_output(
        ["git", "diff", "--name-status", base, head],
        cwd=str(root),
        text=True,
    )
    rows: List[Tuple[str, List[str]]] = []
    for line in out.splitlines():
        row = line.strip()
        if not row:
            continue
        cols = row.split("\t")
        status = cols[0]
        paths = cols[1:]
        rows.append((status, paths))
    return rows


def detect_new_phases_from_diff(rows: Sequence[Tuple[str, List[str]]]) -> Set[str]:
    phases: Set[str] = set()
    pattern = re.compile(r"^docs/dod/DOD__(.+)\.md$")
    for status, paths in rows:
        if not paths:
            continue
        is_add_like = status.startswith("A") or status.startswith("R") or status.startswith("C")
        if not is_add_like:
            continue
        candidate = paths[-1].replace("\\", "/")
        m = pattern.match(candidate)
        if not m:
            continue
        phases.add(normalize_phase_id(m.group(1)))
    return phases


def detect_new_modules_from_diff(rows: Sequence[Tuple[str, List[str]]]) -> Set[str]:
    modules: Set[str] = set()
    for status, paths in rows:
        if not paths:
            continue
        if not (status.startswith("A") or status.startswith("R") or status.startswith("C")):
            continue
        rel = paths[-1].replace("\\", "/")
        if not rel.startswith("modules/"):
            continue
        parts = rel.split("/")
        if len(parts) < 2:
            continue
        modules.add(parts[1])
    return modules


def validate_new_phase(phase_id: str, root: Path, registry_phase_ids: Set[str]) -> PhaseCheckResult:
    pid = normalize_phase_id(phase_id)
    expected = expected_phase_paths(pid)
    errors: List[str] = []
    if not PHASE_RE.match(pid):
        errors.append(f"invalid phase id format: {pid}")

    for key in ("dod", "test_stub", "proof_harness"):
        rel = expected[key]
        if not (root / rel).exists():
            errors.append(f"missing {key}: {rel}")

    if pid not in registry_phase_ids:
        errors.append(f"missing registry entry in {expected['registry']}: {pid}")

    return PhaseCheckResult(phase_id=pid, ok=not errors, errors=errors, expected_paths=expected)


def validate_modules(modules: Iterable[str], root: Path) -> List[str]:
    errors: List[str] = []
    for module in sorted(set(modules)):
        if not MODULE_RE.match(module):
            errors.append(f"invalid module name: modules/{module}")
            continue
        module_root = root / "modules" / module
        if not module_root.exists():
            errors.append(f"module path missing: modules/{module}")
            continue
        readme = module_root / "README.md"
        if not readme.exists():
            errors.append(f"missing module README: modules/{module}/README.md")
    return errors


def _as_dict(results: Sequence[PhaseCheckResult], module_errors: Sequence[str]) -> Dict[str, Any]:
    return {
        "ok": all(r.ok for r in results) and not module_errors,
        "phases": [
            {"phase_id": r.phase_id, "ok": r.ok, "errors": r.errors, "expected_paths": r.expected_paths}
            for r in results
        ],
        "module_errors": list(module_errors),
    }


def _print_human(report: Dict[str, Any]) -> None:
    status = "PASS" if report["ok"] else "FAIL"
    print(f"phase_growth_guard: {status}")
    for item in report["phases"]:
        phase_status = "PASS" if item["ok"] else "FAIL"
        print(f"{item['phase_id']}: {phase_status}")
        for err in item["errors"]:
            print(f"  - {err}")
    if report["module_errors"]:
        print("module errors:")
        for err in report["module_errors"]:
            print(f"  - {err}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase/module growth guard")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Registry YAML path")
    parser.add_argument("--check-diff", action="store_true", help="Check newly introduced phases/modules in git diff")
    parser.add_argument("--base", help="Base ref for --check-diff")
    parser.add_argument("--head", help="Head ref for --check-diff")
    parser.add_argument("--phase", action="append", dest="phases", help="Explicit phase ID to validate")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    args = parser.parse_args(argv)

    root = _repo_root()
    registry_path = root / args.registry
    registry_phase_ids = load_registry_phase_ids(registry_path)

    phase_ids: Set[str] = {normalize_phase_id(x) for x in (args.phases or []) if x and x.strip()}
    modules: Set[str] = set()

    if args.check_diff:
        if not args.base or not args.head:
            parser.error("--check-diff requires --base and --head")
        rows = _diff_name_status(root, args.base, args.head)
        phase_ids.update(detect_new_phases_from_diff(rows))
        modules.update(detect_new_modules_from_diff(rows))

    if not phase_ids and not modules:
        report = {"ok": True, "phases": [], "module_errors": [], "message": "no new phases/modules detected"}
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print("phase_growth_guard: PASS (no new phases/modules detected)")
        return 0

    results = [validate_new_phase(pid, root, registry_phase_ids) for pid in sorted(phase_ids)]
    module_errors = validate_modules(modules, root)
    report = _as_dict(results, module_errors)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)

    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
