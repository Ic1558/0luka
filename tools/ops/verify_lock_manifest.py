#!/usr/bin/env python3
# tools/ops/verify_lock_manifest.py
# Compatibility wrapper for governance_file_lock.py. No hardcoded paths.

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

def main():
    script_path = ROOT / "tools/ops/governance_file_lock.py"
    if not script_path.exists():
        print(f"ERROR: Governance lock script not found at {script_path}", file=sys.stderr)
        sys.exit(1)
    
    # Map --update or -u to --build-manifest
    # And proxy everything else
    args = sys.argv[1:]
    new_args = []
    for arg in args:
        if arg in ["--update", "-u"]:
            new_args.append("--build-manifest")
        else:
            new_args.append(arg)
            
    # Default to verify if no args provided? 
    # But based on user command, they used --update.
    
    cmd = [sys.executable, str(script_path)] + new_args
    sys.exit(subprocess.call(cmd))

if __name__ == "__main__":
    main()
