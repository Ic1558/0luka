#!/bin/zsh
# 0luka STL Seal Script v1.0

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"
STL_ROOT="$ROOT/observability/stl"
GOV_GROUP="staff" # In a real system, this would be _0luka_gov

echo "[FS SEAL] Hardening STL permissions at $STL_ROOT"

# 1. Reset ownership
# chown -R icmini:$GOV_GROUP "$STL_ROOT"

# 2. Set directory permissions: Owner=rwx, Group=rwx, Others=none
# This prevents other users from reading/writing
chmod -R 770 "$STL_ROOT"

# 3. Deny direct write to individuals (ACL)
# Note: On macOS, we can use chmod +a
echo "[FS SEAL] Applying ACL Deny to icmini for tasks/open"
chmod +a "user:icmini:deny write,append,delete" "$STL_ROOT/tasks/open"
chmod +a "user:icmini:deny write,append,delete" "$STL_ROOT/evidence"

echo "[FS SEAL] System status: SEALED"
ls -le "$STL_ROOT" | grep -A 1 "tasks/open"
