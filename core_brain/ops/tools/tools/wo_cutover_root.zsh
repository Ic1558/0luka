#!/usr/bin/env zsh
# WO-PHASE-F-CUTOVER-ROOT-260124

set -euo pipefail

# Path Definitions
OLD_ROOT_1="/Users/icmini/LocalProjects/02luka_local_g"
OLD_ROOT_2="/Users/icmini/02luka"
NEW_ROOT="${ROOT:-$HOME/0luka}"
NEW_ROOT="${NEW_ROOT%/}"
AGENTS_DIR="$HOME/Library/LaunchAgents"
BACKUP_DIR="$HOME/0luka/artifacts/backups/plist_migration_$(date +%s)"

echo "--- 1. Creating Backup ---"
mkdir -p "$BACKUP_DIR"
cp "$AGENTS_DIR"/*.plist "$BACKUP_DIR/" 2>/dev/null || echo "No plists to backup"
echo "✓ Backed up plists to: $BACKUP_DIR"

echo "\n--- 2. Purging Legacy Paths in Plists ---"
# Replacement 1: LocalProjects -> 0luka
find "$AGENTS_DIR" -name "*.plist" -type f -print0 | xargs -0 sed -i '' "s|$OLD_ROOT_1|$NEW_ROOT|g" 2>/dev/null || true
# Replacement 2: 02luka -> 0luka  
find "$AGENTS_DIR" -name "*.plist" -type f -print0 | xargs -0 sed -i '' "s|$OLD_ROOT_2|$NEW_ROOT|g" 2>/dev/null || true
echo "✓ Paths consolidated to $NEW_ROOT"

echo "\n--- 3. Reloading Services (Sync RAM with Disk) ---"
# Only reload com.02luka and com.0luka services
PLISTS_TO_RELOAD=($(ls "$AGENTS_DIR" 2>/dev/null | grep -E "com.0luka|com.02luka" || true))

for plist_name in "${PLISTS_TO_RELOAD[@]}"; do
    plist_path="$AGENTS_DIR/$plist_name"
    label=$(basename "$plist_name" .plist)
    echo "Reloading: $plist_name"
    launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$plist_path" 2>/dev/null || true
done

echo "\n--- 4. Final Cleanup (PID Exorcism) ---"
# Kill any remaining processes referencing old paths
ps aux | grep -E "02luka|LocalProjects" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || echo "No legacy processes found"

echo "\n--- 5. Verification ---"
echo "Remaining legacy strings in LaunchAgents:"
LEGACY_COUNT=$(grep -r "LocalProjects\|02luka" "$AGENTS_DIR" 2>/dev/null | wc -l | tr -d ' ')
echo "Count: $LEGACY_COUNT"

if [ "$LEGACY_COUNT" -eq 0 ]; then
    echo "✅ SUCCESS: Split-brain eliminated"
else
    echo "⚠️  WARNING: $LEGACY_COUNT legacy references remain"
fi
