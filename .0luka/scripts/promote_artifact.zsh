#!/usr/bin/env zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

die(){ print -r -- "ERROR: $*" >&2; exit 1; }
say(){ print -r -- "• $*"; }

ws_id="${1:-}"
[[ -n "$ws_id" ]] || die "Usage: promote_artifact.zsh <workspace_id>"

ws_path="workspaces/${ws_id}"

manifest="${ws_path}/manifest.json"
json_get() { python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))" "$manifest" "$1"; }
[[ -d "$ws_path" ]] || die "Workspace not found: $ws_path"
[[ -f "$ws_path/manifest.json" ]] || die "Invalid workspace (missing manifest.json): $ws_path"

# Build patch evidence using git diff --no-index between core and core_mirror
mkdir -p artifacts/pending artifacts/archive

patch_file="artifacts/pending/${ws_id}.patch"
git diff --no-index -- core/ "${ws_path}/core_mirror/" > "$patch_file" || true

if [[ ! -s "$patch_file" ]]; then
  die "No changes detected between core/ and ${ws_path}/core_mirror/. Nothing to promote."
fi

say "Patch generated: $patch_file"
say "Preview (first 80 lines):"
sed -n '1,80p' "$patch_file" || true
print -r -- ""
read -q "REPLY?Apply this promotion to Kernel (core/)? (y/N) "
print -r -- ""
[[ "${REPLY:-n}" == "y" || "${REPLY:-n}" == "Y" ]] || die "Cancelled."

# Apply by syncing core_mirror back into core (non-destructive: no delete)
say "Applying changes into core/ (rsync -a, no delete)"
rsync -a "${ws_path}/core_mirror/" core/

# Stage only core/
git add core/

# Create archived evidence from staged diff (stronger audit)
arch_ts="$(date +%y%m%d_%H%M%S)"
arch_patch="artifacts/archive/${ws_id}_${arch_ts}.patch"
git diff --cached > "$arch_patch" || true

# Promotion commit (bypass pre-commit using env)
task="$(python3 - <<'PY' "$ws_path/manifest.json"
import json,sys
print(json.load(open(sys.argv[1])).get("task",""))
PY
)"
model="$(python3 - <<'PY' "$ws_path/manifest.json"
import json,sys
print(json.load(open(sys.argv[1])).get("model",""))
PY
)"
trace_id="$(python3 - <<'PY' "$ws_path/manifest.json"
import json,sys
print(json.load(open(sys.argv[1])).get("trace_id",""))
PY
)"

export OLUKA_PROMOTION_MODE=1
msg1="promote(core): ${task:-${ws_id}}"
msg2="workspace: ${ws_id}"
msg3="model: ${model:-unknown} | trace_id: ${trace_id:-none}"
git commit -m "$msg1" -m "$msg2" -m "$msg3"

# Move pending patch to archive (keep both)
mv -f "$patch_file" "artifacts/archive/" || true

# Push (pre-push will enforce sync)
say "Pushing to origin..."
git push

# Cleanup workspace (optional safety: archive rather than delete if you want)
read -q "REPLY2?Cleanup workspace now? (y/N) "
print -r -- ""
if [[ "${REPLY2:-n}" == "y" || "${REPLY2:-n}" == "Y" ]]; then
  rm -rf "$ws_path"
  say "Workspace removed: $ws_path"
else
  say "Workspace kept: $ws_path"
fi

say "DONE. Promotion complete."
