#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

_RULES = [
    ("unix_home", re.compile(r"/Users/")),
    ("windows_home", re.compile(r"C:\\\\Users\\\\")),
    ("unc_path", re.compile(r"^\\\\\\\\[^\\]+\\[^\\]+")),
    ("file_users_uri", re.compile(r"file:///Users/")),
]


def find_hardpath_violations(data: Any, path: str = "") -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    if isinstance(data, dict):
        for key, val in data.items():
            next_path = f"{path}/{key}" if path else f"/{key}"
            issues.extend(find_hardpath_violations(val, next_path))
        return issues
    if isinstance(data, list):
        for idx, val in enumerate(data):
            next_path = f"{path}/{idx}" if path else f"/{idx}"
            issues.extend(find_hardpath_violations(val, next_path))
        return issues
    if isinstance(data, str):
        for rule, pattern in _RULES:
            if pattern.search(data):
                issues.append({"path": path or "/", "rule": rule, "value": data})
                break
    return issues


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: no_hardpath_guard.py <json_file>")
        return 64
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    issues = find_hardpath_violations(payload)
    print(json.dumps({"ok": not issues, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
