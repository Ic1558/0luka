#!/usr/bin/env zsh
set -euo pipefail

# Governance Enforcer: Script Policy
# Moves loose scripts in repo root to Retention Enclave.
# Policy: ops/governance/promotion_sop.md

ROOT="${HOME}/0luka"
DATE_PREFIX="$(date +%y%m%d)"
RETENTION_SCRIPTS="${ROOT}/observability/antigravity_tmp/scripts"
RETENTION_ARTIFACTS="${ROOT}/observability/antigravity_tmp/artifacts"
BEACON="${ROOT}/observability/stl/ledger/global_beacon.jsonl"

mkdir -p "$RETENTION_SCRIPTS" "$RETENTION_ARTIFACTS"

echo "== Script Policy Enforcer =="
echo "Scanning for loose scripts in $ROOT ..."

# Find loose scripts in root only (maxdepth 1)
# Exclude .files, directories
typeset -a loose_files
loose_files=($(find "$ROOT" -maxdepth 1 -type f \( -name "*.zsh" -o -name "*.sh" -o -name "*.py" \) -not -name ".*"))

if (( ${#loose_files} == 0 )); then
    echo "✅ Clean. No loose scripts found in root."
    exit 0
fi

echo "⚠️ Found ${#loose_files} policy violations:"

for f in "${loose_files[@]}"; do
    base="$(basename "$f")"
    
    # Check if already has matching date prefix (simple heuristic)
    if [[ "$base" =~ ^[0-9]{6}_ ]]; then
        target_name="$base"
    else
        target_name="${DATE_PREFIX}_${base}"
    fi
    
    target_path="${RETENTION_SCRIPTS}/${target_name}"
    artifact_path="${RETENTION_ARTIFACTS}/${base%.*}"
    
    echo "   Running enforcement: $base -> $target_name"
    
    # 1. Create artifact stub if needed
    mkdir -p "$artifact_path"
    
    # 2. Move file
    mv "$f" "$target_path"
    
    # 3. Log to Beacon (Audit)
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    entry="{\"ts\": \"$ts\", \"event\": \"policy_enforcement\", \"rule\": \"script_retention\", \"moved\": \"$base\", \"to\": \"$target_name\"}"
    echo "$entry" >> "$BEACON"
done

echo
echo "✅ Enforcement Complete. Violations moved to Retention Area."
echo "See: ops/governance/promotion_sop.md"
