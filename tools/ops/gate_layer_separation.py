#!/usr/bin/env python3

import argparse
import ast
import os
import sys
from pathlib import Path

# Paths to restrict
RESTRICTED_LAYER2_PATHS = ["mission_control"]

# Forbidden core write modules
FORBIDDEN_CORE_MODULES = [
    "core.dispatch",
    "core.submit",
    "core.interface.inbox",
    "core.write",
    "core/dispatch",
    "core/submit",
    "core/interface/inbox",
    "core/write"
]

def check_python_file(path: Path) -> list[str]:
    errors = []
    try:
        content = path.read_text("utf-8")
        tree = ast.parse(content, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in FORBIDDEN_CORE_MODULES:
                        if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                            errors.append(f"Forbidden import '{alias.name}' at line {node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in FORBIDDEN_CORE_MODULES:
                        if node.module == forbidden or node.module.startswith(forbidden + "."):
                            errors.append(f"Forbidden import from '{node.module}' at line {node.lineno}")
    except Exception:
        pass # Ignore parse errors
    return errors

def check_js_file(path: Path) -> list[str]:
    errors = []
    try:
        lines = path.read_text("utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            if "import " in line or "require(" in line:
                for forbidden in FORBIDDEN_CORE_MODULES:
                    if forbidden in line:
                        errors.append(f"Forbidden import '{forbidden}' found at line {i}")
    except Exception:
        pass
    return errors

def main() -> int:
    parser = argparse.ArgumentParser(description="Gate Layer Separation")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    all_errors = {}

    for layer2_dir in RESTRICTED_LAYER2_PATHS:
        layer2_path = root / layer2_dir
        if not layer2_path.exists():
            continue

        for path in layer2_path.rglob("*"):
            if not path.is_file():
                continue
            
            rel_path = path.relative_to(root).as_posix()
            errors = []
            if path.suffix in [".py"]:
                errors = check_python_file(path)
            elif path.suffix in [".js", ".jsx", ".ts", ".tsx"]:
                errors = check_js_file(path)
            
            if errors:
                all_errors[rel_path] = errors

    if all_errors:
        print("LAYER_SEPARATION_GATE: FAIL")
        for file, errors in all_errors.items():
            print(f"File: {file}")
            for err in errors:
                print(f"  - {err}")
        return 1

    print("LAYER_SEPARATION_GATE: PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
