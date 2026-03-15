#!/usr/bin/env python3
"""
tools/ops/git_safety_guard.py
0luka Git Safety Guard — ADR-GIT-001

Scans active 0luka automation code for forbidden git maintenance commands
and direct .git metadata path manipulation. Intended to run in CI and
as a pre-claim gate step.

Also checks the launchd entrypoint registry to detect stale plist targets
pointing to files that no longer exist on disk.

Exit codes:
  0 = clean (no violations)
  1 = violations found (blocks commit/claim)
  2 = usage error

Usage:
  python3 tools/ops/git_safety_guard.py [--scan] [--json]
  python3 tools/ops/git_safety_guard.py --check-registry
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Commands that must NEVER appear in automation that runs against the live
# canonical 0luka repo. Each maintenance command must operate on an isolated
# clone only.
#
# INCIDENT NOTE (2026-03-16): `git clean -fdx` was the confirmed deletion
# mechanism for repos/option/modules/antigravity/realtime/control_tower.py.
# The command was run interactively as:
#   git reset --hard 0luka-runtime-v1 && git clean -fdx
# This wiped all untracked files from the working tree including live
# application source files that were never committed. See ADR-GIT-001.
FORBIDDEN_MAINTENANCE_COMMANDS: list[str] = [
    "git gc",
    "git repack",
    "git prune",
    "git clean",        # catches all git clean variants including -fd, -fdx, -fdX
    "git clean -fd",    # explicit: removes untracked non-ignored files — deletes live source
    "git clean -fdx",   # explicit: removes ALL untracked including non-ignored — CONFIRMED INCIDENT CAUSE
    "git clean -fdX",   # explicit: removes only gitignored files
    "git worktree prune",
    "git filter-repo",
    "git filter-branch",
    "git fsck",          # read-only but heavy — flag for review
]

# Regex patterns for direct .git metadata path manipulation.
# rm/rmtree/shutil.rmtree/mv targeting these paths is always forbidden
# in automation code.
PROTECTED_GIT_PATHS: list[str] = [
    r"\.git/objects",
    r"\.git/objects/pack",
    r"\.git/index",
    r"\.git/packed-refs",
    r"\.git/worktrees",
    r"\.git/hooks",
    r"\.git/config",
    r"\.git/HEAD",
]

# Patterns combining destructive operations + protected paths
DESTRUCTIVE_PATH_PATTERNS: list[re.Pattern] = [
    # rm -rf .git/... style
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|--force\s+).*\.git[/\\]"),
    # shutil.rmtree / os.remove / os.unlink targeting .git
    re.compile(r"(shutil\.rmtree|os\.remove|os\.unlink|os\.rmdir)\s*\(.*\.git[/\\]"),
    # mv / os.rename targeting .git
    re.compile(r"\bmv\b.*\.git[/\\]"),
    re.compile(r"(os\.rename|os\.replace|shutil\.move)\s*\(.*\.git[/\\]"),
    # Direct pack deletion
    re.compile(r"(rm|unlink|remove).*objects/pack"),
]

# ---------------------------------------------------------------------------
# Scan targets: active code only (not staging, not archive)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent  # ~/0luka

SCAN_EXTENSIONS = {".py", ".zsh", ".sh"}
SCAN_EXCLUDES = {
    "staging",
    "observability/archive",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "node_modules",
}

# Files that are intentional, reviewed git-operation wrappers.
# These are operator-triggered (not automation-invoked via launchd) and
# have their own safety guards. Exempt from the scanner.
SCAN_EXEMPT_FILES = {
    "tools/ops/git_safety_guard.py",          # this file — would self-flag its own constants
    "system/tools/git/safe_git_clean.zsh",    # controlled wrapper: -X ignored-only, dry-run default, guard check
    "tools/rollback_git_commit.zsh",          # explicit operator-triggered revert tool
    "tools/ops/proofs/pack8/gmx_step8_pack8_seal.zsh",   # manual proof seal scripts (not launchd)
    "tools/ops/proofs/pack7/gmx_step7_pack7_seal.zsh",
    "tools/ops/proofs/pack9/gmx_step9_pack9_seal.zsh",
    ".0luka/scripts/promote_artifact.zsh",    # explicit human-operator promotion script
    ".0luka/scripts/new_workspace.zsh",       # workspace setup — operator-triggered
}

# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def _should_skip(path: Path) -> bool:
    rel = str(path.relative_to(ROOT))
    for excl in SCAN_EXCLUDES:
        if excl in rel:
            return True
    if rel in SCAN_EXEMPT_FILES:
        return True
    return False


def scan_file(path: Path) -> list[dict]:
    """Return list of violation dicts for a single file."""
    violations = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return violations

    lines = text.splitlines()
    rel = str(path.relative_to(ROOT))

    for lineno, line in enumerate(lines, 1):
        # Check forbidden maintenance commands
        for cmd in FORBIDDEN_MAINTENANCE_COMMANDS:
            if cmd in line:
                # Skip comment lines unless it's an actual execution
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Skip lines that are just checking/echoing the command
                if stripped.startswith("echo ") or stripped.startswith("say "):
                    continue
                violations.append({
                    "file": rel,
                    "line": lineno,
                    "type": "forbidden_maintenance_command",
                    "match": cmd,
                    "text": line.strip()[:120],
                })

        # Check destructive + protected path patterns
        for pat in DESTRUCTIVE_PATH_PATTERNS:
            if pat.search(line):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                violations.append({
                    "file": rel,
                    "line": lineno,
                    "type": "destructive_git_path_operation",
                    "match": pat.pattern,
                    "text": line.strip()[:120],
                })

    return violations


def scan_repo() -> list[dict]:
    """Scan all active automation files in 0luka for git safety violations."""
    all_violations = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SCAN_EXTENSIONS:
            continue
        if _should_skip(path):
            continue
        all_violations.extend(scan_file(path))
    return all_violations


# ---------------------------------------------------------------------------
# Registry check
# ---------------------------------------------------------------------------

REGISTRY_PATH = ROOT / "docs" / "architecture" / "launchd_entrypoint_registry.yaml"


def check_registry() -> list[dict]:
    """
    Check launchd_entrypoint_registry.yaml for ACTIVE entries whose target
    file does not exist on disk. Returns list of issue dicts.
    """
    issues = []

    if not REGISTRY_PATH.exists():
        issues.append({
            "type": "registry_missing",
            "message": f"Registry not found: {REGISTRY_PATH}",
        })
        return issues

    if not _YAML_AVAILABLE:
        issues.append({
            "type": "yaml_unavailable",
            "message": "pyyaml not installed — cannot check registry. Run: pip install pyyaml",
        })
        return issues

    try:
        with open(REGISTRY_PATH) as f:
            data = _yaml.safe_load(f)
    except Exception as e:
        issues.append({"type": "registry_parse_error", "message": str(e)})
        return issues

    entries = data.get("entrypoints", [])
    for entry in entries:
        status = entry.get("status", "")
        if status != "ACTIVE":
            continue  # only check entries expected to be live
        target = entry.get("target_path", "")
        if not target:
            continue
        target_path = ROOT / target
        if not target_path.exists():
            issues.append({
                "type": "stale_plist_target",
                "id": entry.get("id", "unknown"),
                "plist": entry.get("plist", "unknown"),
                "target_path": target,
                "message": f"ACTIVE entry '{entry.get('id')}' target does not exist: {target}",
            })

    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="0luka Git Safety Guard — scan for forbidden git operations"
    )
    parser.add_argument("--scan", action="store_true", default=False,
                        help="Scan active automation files for forbidden git commands")
    parser.add_argument("--check-registry", action="store_true", default=False,
                        help="Check launchd_entrypoint_registry.yaml for stale targets")
    parser.add_argument("--json", action="store_true", default=False,
                        help="Output results as JSON")
    parser.add_argument("--file", type=str, default=None,
                        help="Scan a single file instead of the full repo")
    args = parser.parse_args()

    # Default to --scan if no mode specified
    if not args.scan and not args.check_registry and not args.file:
        args.scan = True

    all_results: dict = {}
    exit_code = 0

    # --- code scanner ---
    if args.file or args.scan:
        if args.file:
            target = Path(args.file).resolve()
            if not target.exists():
                print(f"[git_safety_guard] ERROR: file not found: {args.file}", file=sys.stderr)
                return 2
            violations = scan_file(target)
        else:
            violations = scan_repo()
        all_results["scan"] = {"violations": violations, "count": len(violations)}
        if violations:
            exit_code = 1

    # --- registry check ---
    if args.check_registry:
        issues = check_registry()
        all_results["registry"] = {"issues": issues, "count": len(issues)}
        if issues:
            exit_code = 1

    if args.json:
        print(json.dumps(all_results, indent=2))
        return exit_code

    # human-readable output
    if "scan" in all_results:
        violations = all_results["scan"]["violations"]
        if violations:
            print(f"[git_safety_guard] SCAN FAIL — {len(violations)} violation(s):\n")
            for v in violations:
                print(f"  {v['file']}:{v['line']}  [{v['type']}]")
                print(f"    match : {v['match']}")
                print(f"    line  : {v['text']}")
                print()
            print("See: docs/architecture/adr/ADR-GIT-001-git-safety-rules.md")
        else:
            print("[git_safety_guard] SCAN PASS — no forbidden git operations in active automation.")

    if "registry" in all_results:
        issues = all_results["registry"]["issues"]
        if issues:
            print(f"\n[git_safety_guard] REGISTRY FAIL — {len(issues)} stale target(s):\n")
            for iss in issues:
                print(f"  [{iss['type']}] {iss.get('message', '')}")
            print("\nResolve before running git clean. See: docs/architecture/launchd_entrypoint_registry.yaml")
        else:
            print("[git_safety_guard] REGISTRY PASS — all ACTIVE entrypoint targets present on disk.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
