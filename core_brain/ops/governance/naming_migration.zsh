#!/zsh
# 0luka Canonical Naming Migration v1.0
# Translates YYYYMMDD -> YYMMDD and adds HASH8 if missing.

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"
TASK_DIR="$ROOT/observability/stl/tasks/open"
EVID_DIR="$ROOT/observability/stl/evidence"

function get_hash8() {
    cat "$1" | shasum -a 256 | cut -c1-8
}

function migrate_file() {
    local file="$1"
    local dir="$(dirname "$file")"
    local base="$(basename "$file")"
    
    # Pattern 1: T-YYYYMMDD-XXX_slug.yaml -> YYMMDD_HHMMSS_task_slug_HASH8.yaml
    if [[ $base =~ ^T-([0-9]{4})([0-9]{2})([0-9]{2})-(.*)\.yaml$ ]]; then
        local yy="${match[1]:2:2}"
        local mm="${match[2]}"
        local dd="${match[3]}"
        local slug="${match[4]}"
        local h8=$(get_hash8 "$file")
        # Use current time as fallback for HHMMSS since legacy IDs lack precision
        local hhmmss=$(date +%H%M%S)
        local new_name="${yy}${mm}${dd}_${hhmmss}_task_${slug}_${h8}.yaml"
        echo "Migrating Task: $base -> $new_name"
        mv "$file" "$dir/$new_name"
    fi
    
    # Pattern 2: attestation.json inside T-... folder
    # We rename the folder first, then the file inside.
}

# 1. Migrate task folders and files
echo "== Migrating Open Tasks =="
for f in $TASK_DIR/T-*; do
    [ -f "$f" ] && migrate_file "$f"
done

# 2. Migrate evidence folders
echo "== Migrating Evidence Folders =="
for d in $EVID_DIR/T-*; do
    if [ -d "$d" ]; then
        local base="$(basename "$d")"
        if [[ $base =~ ^T-([0-9]{4})([0-9]{2})([0-9]{2})-(.*)$ ]]; then
            local yy="${match[1]:2:2}"
            local mm="${match[2]}"
            local dd="${match[3]}"
            local slug="${match[4]}"
            local hhmmss=$(date +%H%M%S)
            
            # Look at attestation.json inside to get hash
            local h8="00000000"
            [ -f "$d/attestation.json" ] && h8=$(get_hash8 "$d/attestation.json")
            
            local new_dir="${yy}${mm}${dd}_${hhmmss}_attnfolder_${slug}_${h8}"
            echo "Migrating Evidence Dir: $base -> $new_dir"
            mv "$d" "$EVID_DIR/$new_dir"
            
            # Rename internal file to canonical attn
            if [ -f "$EVID_DIR/$new_dir/attestation.json" ]; then
                mv "$EVID_DIR/$new_dir/attestation.json" "$EVID_DIR/$new_dir/${yy}${mm}${dd}_${hhmmss}_attn_${slug}_${h8}.json"
            fi
        fi
    fi
done

echo "✅ Migration Complete"
