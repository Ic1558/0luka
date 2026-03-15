"""Warn about new legacy result-field readers (AG-17C3A)."""

from __future__ import annotations

import argparse
import builtins
import os
import re
from pathlib import Path

# Files excluded from scanning — these are the helper layer itself.
# result_reader.py reads FROM the execution_envelope dict (that is correct envelope-first reads).
# result_integrity.py reads both sides intentionally to compare them (mirror consistency check).
SKIP_FILES = {
    "core/result_reader.py",
    "core/result_integrity.py",
    # circuit_breaker uses envelope-first (get_result_status) with legacy fallback for
    # pre-envelope results (router.execute never returns execution_envelope directly).
    "core/circuit_breaker.py",
}
SKIP_DIRS = {"tools/guards"}
LEGACY_KEYS = ["status", "summary", "provenance", "seal", "evidence"]
PATTERN = re.compile(r"result\s*\[\s*[\'\"]({})[\'\"]\s*\]".format("|".join(LEGACY_KEYS)))


def scan_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    matches = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if PATTERN.search(line):
            matches.append(f"{path}:{idx}: {line.strip()}")
        elif ".get(" in line and any(f"\"{key}\"" in line for key in LEGACY_KEYS):
            matches.append(f"{path}:{idx}: {line.strip()}")
    return matches


def main(directory: str) -> int:
    root = Path(directory)
    findings = []
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.samefile(Path(__file__)):
            continue
        # Skip helper layer self-reads — these are intentional envelope-first reads
        try:
            rel = str(path.relative_to(Path.cwd()))
        except ValueError:
            rel = str(path)
        if any(rel.endswith(skip) or rel == skip for skip in SKIP_FILES):
            continue
        matches = scan_file(path)
        findings.extend(matches)
    if findings:
        print("check_result_reader_usage: FAIL - direct legacy reads detected:")
        for entry in findings:
            print(entry)
        return 1
    print("check_result_reader_usage: PASS - no direct legacy reads detected")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default=".")
    args = parser.parse_args()
    raise SystemExit(main(args.directory))
