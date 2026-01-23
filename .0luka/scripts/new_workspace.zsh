#!/usr/bin/env zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

die(){ print -r -- "ERROR: $*" >&2; exit 1; }
say(){ print -r -- "• $*"; }

task="${1:-}"
model="${2:-gemini}"

[[ -n "$task" ]] || die "Usage: new_workspace.zsh <task_slug> [model=gemini|claude]"
[[ -d ".git" ]] || die "Not a git repo"

# Sync first (anti context drift)
say "Sync: git pull --rebase"
git pull --rebase

ts="$(date +%y%m%d_%H%M%S)"
ws_id="ws_${ts}_${task}"
ws_path="workspaces/${ws_id}"

trace_id="$(uuidgen 2>/dev/null || date +%s%N)"
base_commit="$(git rev-parse HEAD)"

mkdir -p "${ws_path}/input" "${ws_path}/work" "${ws_path}/output" "${ws_path}/runs" "${ws_path}/core_mirror" "${ws_path}/rules" "${ws_path}/artifacts"

# Inject kernel mirror (copy, not link)
rsync -a --exclude='.git' core/ "${ws_path}/core_mirror/" || true

# Inject rules if present
if [[ -d "catalog/rules" ]]; then
  rsync -a "catalog/rules/" "${ws_path}/rules/" || true
fi

cat > "${ws_path}/manifest.json" <<JSON
{
  "workspace_id": "${ws_id}",
  "task": "${task}",
  "model": "${model}",
  "trace_id": "${trace_id}",
  "created_at": "$(date +%Y-%m-%dT%H:%M:%S%z)",
  "base_commit": "${base_commit}",
  "status": "active"
}
JSON
chmod 644 "${ws_path}/manifest.json" 2>/dev/null || true
say "Workspace ready: ${ws_path}"
say "Next: work inside ${ws_path}/ (Agent writes there), then promote:"
say "  .0luka/scripts/promote_artifact.zsh ${ws_id}"
