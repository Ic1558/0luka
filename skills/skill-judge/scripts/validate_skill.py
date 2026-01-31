#!/usr/bin/env python3
import sys
import os
import yaml
import re

def parse_frontmatter(content):
    match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        print(f"YAML Error: {e}")
        return None

def validate_skill(filepath):
    print(f"Judging: {filepath}")
    
    if not os.path.exists(filepath):
        print("❌ File not found.")
        return False

    with open(filepath, 'r') as f:
        content = f.read()

    errors = []

    # 1. Frontmatter Check
    meta = parse_frontmatter(content)
    if not meta:
        errors.append("Missing or invalid YAML frontmatter (--- ... ---)")
    else:
        required_keys = ["name", "version", "category", "owner", "sot"]
        for key in required_keys:
            if key not in meta:
                errors.append(f"Frontmatter missing required key: '{key}'")

    # 2. Section Checks
    required_sections = [
        "## 1. Identity",
        "## 2.", # Loose check for sections
        "## 3.",
    ]
    for section in required_sections:
        if section not in content:
            errors.append(f"Missing Markdown Section: '{section}'")

    # 3. Specific Logic for Liam/GMX
    if "liam" in filepath.lower() and "sot: true" not in content.lower():
         errors.append("SOT flag must be true or present in frontmatter.")

    # Report
    if errors:
        print("❌ VALIDATION FAILED")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ VALIDATION PASSED (SOT Compliant)")
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_skill.py <path_to_skill.md>")
        sys.exit(1)
    validate_skill(sys.argv[1])
