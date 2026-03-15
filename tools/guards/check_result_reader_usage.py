"""Warn about new legacy result-field readers (AG-17C3A)."""

from __future__ import annotations

import argparse
import builtins
import os
import re
from pathlib import Path

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
        matches = scan_file(path)
        findings.extend(matches)
    if findings:
        print("check_result_reader_usage: warning - legacy reads detected:")
        for entry in findings:
            print(entry)
    else:
        print("check_result_reader_usage: no legacy reads detected")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default=".")
    args = parser.parse_args()
    raise SystemExit(main(args.directory))
