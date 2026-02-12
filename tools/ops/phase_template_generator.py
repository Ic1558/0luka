#!/usr/bin/env python3
"""
Phase Template Generator (Step 3 Controlled Spawner)

Creates deterministic scaffold for a new phase:
- DoD doc scaffold
- Registry stub
- Unit test stub
- Proof harness stub
- CI hook binding check
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Sequence

import yaml

DEFAULT_REGISTRY = "core/governance/phase_status.yaml"
DEFAULT_CI_HOOK = ".github/workflows/governance-controls.yml"
PHASE_RE = re.compile(r"^PHASE_[A-Z0-9_]+$")


def normalize_phase_id(phase_id: str) -> str:
    return phase_id.strip().upper()


def phase_slug(phase_id: str) -> str:
    return normalize_phase_id(phase_id).lower()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _scaffold_paths(phase_id: str) -> Dict[str, Path]:
    root = _repo_root()
    slug = phase_slug(phase_id)
    return {
        "dod": root / f"docs/dod/DOD__{phase_id}.md",
        "test": root / f"core/verify/test_{slug}.py",
        "prove": root / f"core/verify/prove_{slug}.py",
        "registry": root / DEFAULT_REGISTRY,
        "ci_hook": root / DEFAULT_CI_HOOK,
    }


def _write_if_missing(path: Path, content: str, dry_run: bool) -> bool:
    if path.exists():
        return False
    if dry_run:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _dod_template(phase_id: str, owner: str, gate: str, sot: str) -> str:
    today = _utc_date()
    return f"""# DoD -- {phase_id}

## 0. Metadata (MANDATORY)
- **Phase / Task ID**: {phase_id}
- **Owner (Actor)**: {owner}
- **Gate**: {gate}
- **Related SOT Section**: {sot}
- **Target Status**: DESIGNED -> PARTIAL -> PROVEN
- **Commit SHA**:
- **Date**: {today}

## 1. Code State (Static Integrity)
- [ ] Feature implemented (commit referenced)
- [ ] Lint/tests pass

## 2. Evidence (Fail-Closed Core)
- [ ] Activity event: started
- [ ] Activity event: completed
- [ ] Activity event: verified
- [ ] Evidence artifact path recorded

## Verdict (Strict)
- DESIGNED / PARTIAL / PROVEN
"""


def _test_template(phase_id: str) -> str:
    slug = phase_slug(phase_id)
    return f"""def test_{slug}_scaffold_exists():
    assert True
"""


def _prove_template(phase_id: str) -> str:
    slug = phase_slug(phase_id)
    return f"""def run_{slug}_proof():
    return {{
        "phase": "{phase_id}",
        "status": "DESIGNED",
        "note": "scaffold-only proof harness",
    }}
"""


def _upsert_registry_stub(path: Path, phase_id: str, dry_run: bool) -> bool:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(payload, dict):
        payload = {}
    phases = payload.setdefault("phases", {})
    if not isinstance(phases, dict):
        raise RuntimeError(f"invalid registry schema: {path}")
    if phase_id in phases:
        return False
    phases[phase_id] = {
        "verdict": "DESIGNED",
        "requires": [],
        "last_verified_ts": "",
        "commit_sha": "",
        "evidence_path": "",
    }
    if dry_run:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic phase scaffold")
    parser.add_argument("--phase", required=True, help="Phase ID, e.g. PHASE_16_0")
    parser.add_argument("--owner", default="TBD", help="Owner name in DoD scaffold")
    parser.add_argument("--gate", default="TBD", help="Gate name in DoD scaffold")
    parser.add_argument("--sot", default="core/governance/agents.md", help="Related SOT section")
    parser.add_argument("--dry-run", action="store_true", help="Show intended writes only")
    args = parser.parse_args(argv)

    phase_id = normalize_phase_id(args.phase)
    if not PHASE_RE.match(phase_id):
        raise SystemExit(f"invalid --phase format: {phase_id} (expected ^PHASE_[A-Z0-9_]+$)")

    paths = _scaffold_paths(phase_id)
    if not paths["ci_hook"].exists():
        raise SystemExit(
            f"missing CI hook binding: {paths['ci_hook']} (run governance controls setup first)"
        )

    created = []
    if _write_if_missing(paths["dod"], _dod_template(phase_id, args.owner, args.gate, args.sot), args.dry_run):
        created.append(paths["dod"])
    if _write_if_missing(paths["test"], _test_template(phase_id), args.dry_run):
        created.append(paths["test"])
    if _write_if_missing(paths["prove"], _prove_template(phase_id), args.dry_run):
        created.append(paths["prove"])
    if _upsert_registry_stub(paths["registry"], phase_id, args.dry_run):
        created.append(paths["registry"])

    mode = "DRY_RUN" if args.dry_run else "APPLIED"
    print(f"phase_template_generator: {mode}")
    if created:
        for path in created:
            print(f"  created_or_updated: {path}")
    else:
        print("  no changes (already scaffolded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
