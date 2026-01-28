#!/usr/bin/env zsh
set -euo pipefail

# Governance Enforcer: Script Policy (v1.0)
# Detects and moves loose scripts in repo root to Retention Enclave.
# Policy: ops/governance/promotion_sop.md

# 1. Verification & Defaults
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "${HOME}/0luka")"
DATE_PREFIX="$(date +%y%m%d)"
RETENTION_BASE="${ROOT}/observability/antigravity_tmp"
RETENTION_SCRIPTS="${RETENTION_BASE}/scripts"
RETENTION_ARTIFACTS="${RETENTION_BASE}/artifacts"
BEACON="${ROOT}/observability/stl/ledger/global_beacon.jsonl"
ALLOWLIST="${ROOT}/ops/governance/enforcer_allowlist.txt"

MODE="check" # Default to check mode
INCLUDE_PY=0

# usage
usage() {
    echo "Usage: $0 [--check | --fix] [--include-py]"
    echo "  --check   : Exit 0 if clean, 1 if violations (Default)"
    echo "  --fix     : Move violations to Retention Area"
    echo "  --include-py: Also scan .py files (default: .zsh, .sh)"
    exit 1
}

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --check) MODE="check"; shift ;;
        --fix)   MODE="fix"; shift ;;
        --include-py) INCLUDE_PY=1; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown arg: $1"; usage ;;
    esac
done

echo "== Script Policy Enforcer (Mode: $MODE) =="
echo "Root: $ROOT"

# 2. Build Candidate List
# Safe find using null delimiter
typeset -a loose_files
while IFS= read -r -d '' file; do
    loose_files+=("$file")
done < <(find "$ROOT" -maxdepth 1 -type f \( -name "*.zsh" -o -name "*.sh" $( ((INCLUDE_PY)) && echo "-o -name '*.py'" ) \) -not -name ".*" -print0)

# Load Allowlist
typeset -A allowed_map
if [[ -f "$ALLOWLIST" ]]; then
    while IFS= read -r line; do
        [[ "$line" =~ ^#.* ]] && continue
        [[ -z "$line" ]] && continue
        allowed_map[$line]=1
    done < "$ALLOWLIST"
fi

# 3. Scan & Enforce
violations=0
files_to_move=()

for f in "${loose_files[@]}"; do
    base="$(basename "$f")"
    
    # Check Allowlist
    if [[ -n "${allowed_map[$base]:-}" ]]; then
        continue
    fi
    
    # Violation found
    ((violations++))
    files_to_move+=("$f")
    echo "⚠️  Violation: $base"
done

if (( violations == 0 )); then
    echo "✅ Clean. No policy violations."
    exit 0
fi

echo "Found $violations violations."

if [[ "$MODE" == "check" ]]; then
    echo "Run with --fix to resolve."
    exit 1
fi

# 4. Fix Mode: Execution
mkdir -p "$RETENTION_SCRIPTS"
mkdir -p "$(dirname "$BEACON")"

for f in "${files_to_move[@]}"; do
    base="$(basename "$f")"
    
    # Naming logic
    if [[ "$base" =~ ^[0-9]{6}_ ]]; then
        target_name="$base"
        artifact_dir_name="${base%.*}"
    else
        target_name="${DATE_PREFIX}_${base}"
        artifact_dir_name="${DATE_PREFIX}_${base%.*}"
    fi
    
    target_path="${RETENTION_SCRIPTS}/${target_name}"
    artifact_path="${RETENTION_ARTIFACTS}/${artifact_dir_name}"
    
    echo "   Moving: $base -> $target_name"
    
    # Create matching artifact folder
    mkdir -p "$artifact_path"
    
    # Move
    mv "$f" "$target_path"
    
    # Beacon Log
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    entry="{\"ts\": \"$ts\", \"event\": \"policy_enforcement\", \"rule\": \"script_retention\", \"moved\": \"$base\", \"to\": \"$target_name\"}"
    echo "$entry" >> "$BEACON"
done

echo "✅ Enforcement Complete."
