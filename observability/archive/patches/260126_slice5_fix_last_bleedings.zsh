#!/usr/bin/env zsh
set -euo pipefail

ROOT="$HOME/0luka"

# --- (1) MLS shim path (legacy -> canonical) ---
mkdir -p "$ROOT/g/tools"

cat > "$ROOT/g/tools/mls_file_watcher.zsh" <<'EOF'
#!/usr/bin/env zsh
set -euo pipefail
exec "$HOME/0luka/tools/mls_file_watcher.zsh" "$@"
EOF
chmod +x "$ROOT/g/tools/mls_file_watcher.zsh"
print "OK: created MLS shim at $ROOT/g/tools/mls_file_watcher.zsh"

# --- (2) Liam stub at caller path ---
mkdir -p "$ROOT/system/antigravity/scripts"

cat > "$ROOT/system/antigravity/scripts/liam_engine_worker.py" <<'EOF'
# stub to silence missing-worker spam in clean-room mode
import sys
if __name__ == "__main__":
    sys.exit(0)
EOF
print "OK: created Liam stub at $ROOT/system/antigravity/scripts/liam_engine_worker.py"

# --- (3) Quick checks ---
print ""
print "CHECK: files exist:"
ls -la "$ROOT/g/tools/mls_file_watcher.zsh" "$ROOT/system/antigravity/scripts/liam_engine_worker.py"

print ""
print "NOTE: wait 60-90s then inspect logs:"
print "  tail -n 20 $ROOT/g/logs/mls_watcher.err.log"
print "  tail -n 20 $ROOT/system/antigravity/logs/liam_engine.stderr.log"
