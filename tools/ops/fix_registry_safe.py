#!/usr/bin/env python3
# tools/ops/fix_registry_safe.py
# Safe Registry Restoration Script recommended by Liam
# Logic: Restore names, dedupe IDs, filters junk, preserves valid tools.

import sys
import shutil
import json
from pathlib import Path

# Try importing yaml
try:
    import yaml
except ImportError:
    print("PyYAML needed. pip install pyyaml")
    sys.exit(1)

REGISTRY_PATH = Path("core_brain/catalog/registry.yaml")
BACKUP_PATH = REGISTRY_PATH.with_suffix(".yaml.bak")

def is_junk(path_str):
    """
    Filter logic:
    - Drops __init__.py
    - Drops tools/librarian/* EXCEPT scoring.py, apply.py
    - Drops tests/*
    """
    if path_str.endswith("__init__.py"):
        return True
    
    if "tools/librarian/" in path_str:
        filename = Path(path_str).name
        if filename not in ("scoring.py", "apply.py"):
            return True
            
    if path_str.startswith("tests/"):
        return True
        
    return False

def main():
    if not REGISTRY_PATH.exists():
        print(f"FATAL: {REGISTRY_PATH} not found.")
        sys.exit(1)

    # 1. Backup
    print(f"[SAFE] Backing up to {BACKUP_PATH}...")
    shutil.copy(REGISTRY_PATH, BACKUP_PATH)

    # 2. Read
    with open(REGISTRY_PATH, "r") as f:
        data = yaml.safe_load(f) or []

    print(f"[INFO] Loaded {len(data)} entries.")

    cleaned = []
    dropped = []
    seen_ids = {} # id -> entry
    duplicates = []

    # 3. Process
    tools_list = data.get("tools", [])
    if isinstance(data, list):
         tools_list = data # fallback if someone made it a list

    for entry in tools_list:
        path = entry.get("path", "")
        
        # Filter Junk
        if is_junk(path):
            dropped.append({"reason": "junk_filter", "entry": entry})
            continue

        # Restore Name (if missing, use filename base)
        if not entry.get("name"):
            entry["name"] = Path(path).stem

        # ID Resolution
        # If ID missing, use name.
        tid = entry.get("id") or entry.get("name")
        entry["id"] = tid

        # Deduplication
        if tid in seen_ids:
            # Conflict! Prefer "bridge lane" (tools/bridge/)
            existing = seen_ids[tid]
            existing_path = existing.get("path", "")
            
            # If current is bridge and existing is NOT, replace existing
            if "tools/bridge/" in path and "tools/bridge/" not in existing_path:
                print(f"[DEDUPE] Replacing {tid}: {existing_path} -> {path} (Bridge Preference)")
                duplicates.append({"kept": entry, "dropped": existing})
                seen_ids[tid] = entry
            else:
                # Keep existing, drop current
                print(f"[DEDUPE] Dropping duplicate {tid}: {path} (Kept: {existing_path})")
                duplicates.append({"kept": existing, "dropped": entry})
        else:
            seen_ids[tid] = entry

    # Reconstruct list from unique map
    final_list = list(seen_ids.values())
    
    # Sort for stability
    final_list.sort(key=lambda x: x.get("id", ""))

    # 4. Write Reports
    Path("dropped.json").write_text(json.dumps(dropped, indent=2))
    Path("dups.json").write_text(json.dumps(duplicates, indent=2))
    
    print(f"[INFO] Dropped {len(dropped)} junk entries.")
    print(f"[INFO] Deduped {len(duplicates)} collisions.")
    print(f"[INFO] Final count: {len(final_list)}")

    # 5. Atomic Write
    if isinstance(data, dict):
        data["tools"] = final_list
        output_obj = data
    else:
        output_obj = final_list

    # Standard YAML dump (block style)
    with open(REGISTRY_PATH, "w") as f:
        yaml.safe_dump(output_obj, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print(f"[SUCCESS] Wrote {REGISTRY_PATH}")
    print("Next Steps: Inspect 'dropped.json' and 'dups.json'. Check registry.yaml content.")

if __name__ == "__main__":
    main()
