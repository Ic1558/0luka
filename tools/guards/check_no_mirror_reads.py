"""Enforce envelope-first authority — flag direct mirror reads outside permitted zones.

Authority Freeze (Phase 3): result["status"], result["summary"], result["seal"],
result["provenance"], result["executor"], result["routing"], result["policy"],
result["execution_events"] must not be read as authoritative outside exempt files.

Scan scope: core/*.py production files only (not core/verify/, not core/execution/).
Test files are excluded because 'result' is an overloaded name in test context
(dispatch events, ledger summaries, watchdog state — none are outbox result mirrors).

Permitted zones (read mirrors legitimately by design):
  core/result_integrity.py    — comparison module, reads mirrors intentionally for consistency check
  core/result_reader.py       — detect_result_authority_mismatches reads both for mismatch detection
  core/outbox_writer.py       — writer path, reads/builds the normalized outbox envelope
  core/task_dispatcher.py     — pipeline builder, reads raw executor output (not result mirrors)
  core/phase1d_result_gate.py — gate processor, reads evidence/outputs for enforcement
  core/seal.py                — low-level HMAC sealer reads envelope dict
  core/circuit_breaker.py     — reads circuit-breaker execute result (not outbox result mirror)
  core/cli.py                 — reads dispatch event status (not outbox result mirror)
  core/smoke.py               — reads dispatch result status (not outbox result mirror)
  core/phase1a_emit.py        — reads executor result dict (not outbox result mirror)
  core/remediation_engine.py  — reads watchdog/check result (not outbox result mirror)
  tools/guards/               — guard scripts themselves
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

MIRROR_KEYS = [
    "status", "summary", "seal", "provenance",
    "executor", "routing", "policy", "execution_events",
]

_BRACKET_PAT = re.compile(
    r"""result\s*\[\s*['"]({keys})['"]\s*\]""".format(keys="|".join(MIRROR_KEYS))
)
_GET_PAT = re.compile(
    r"""result\s*\.\s*get\s*\(\s*['"]({keys})['"]""".format(keys="|".join(MIRROR_KEYS))
)

# Files with legitimate mirror reads — documented legacy debt or writer/comparison paths
EXEMPT_FILES = {
    "core/result_integrity.py",
    "core/result_reader.py",
    "core/outbox_writer.py",
    "core/task_dispatcher.py",
    "core/phase1d_result_gate.py",
    "core/seal.py",
    "core/circuit_breaker.py",
    "core/cli.py",
    "core/smoke.py",
    "core/phase1a_emit.py",
    "core/remediation_engine.py",
}

# Directories excluded from scan — test/verify files use 'result' for dispatch events,
# ledger dicts, watchdog state, etc. (not outbox result mirrors)
EXEMPT_DIRS = {
    "tools/guards",
    "core/verify",
    "core/execution",
    "tests",
}


def _is_exempt(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    if any(rel.startswith(d + "/") or rel == d for d in EXEMPT_DIRS):
        return True
    return rel in EXEMPT_FILES


def scan_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []
    findings = []
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if _BRACKET_PAT.search(line) or _GET_PAT.search(line):
            findings.append(f"{path}:{idx}: {stripped}")
    return findings


def main(directory: str) -> int:
    root = Path(directory)
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if _is_exempt(path):
            continue
        violations.extend(scan_file(path))

    if violations:
        print("check_no_mirror_reads: FAIL — direct mirror reads detected outside permitted zones:")
        for v in violations:
            print(f"  {v}")
        return 1

    print("check_no_mirror_reads: PASS — no unauthorized mirror reads detected")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default=str(REPO_ROOT / "core"))
    args = parser.parse_args()
    raise SystemExit(main(args.directory))
