#!/usr/bin/env zsh
set -euo pipefail

ROOT="$HOME/0luka"
EVID="$ROOT/observability/artifacts/root_regen_audit_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$EVID"

echo "== 0) Context ==" | tee "$EVID/00_context.txt"
{
  date
  echo "ROOT=$ROOT"
  echo "PWD=$(pwd)"
  git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || true
} | tee -a "$EVID/00_context.txt"

echo "== 1) Show suspicious root dirs ==" | tee "$EVID/01_root_ls.txt"
ls -la "$ROOT" | tee -a "$EVID/01_root_ls.txt"

echo "== 2) Stat artifacts/ and logs/ (if exist) ==" | tee "$EVID/02_stat.txt"
for d in "$ROOT/artifacts" "$ROOT/logs"; do
  if [[ -e "$d" ]]; then
    echo "--- $d" | tee -a "$EVID/02_stat.txt"
    /usr/bin/stat -x "$d" | tee -a "$EVID/02_stat.txt"
    echo "xattr:" | tee -a "$EVID/02_stat.txt"
    /usr/bin/xattr -l "$d" 2>/dev/null | tee -a "$EVID/02_stat.txt" || true
    echo "recent files (top 50 newest by mtime):" | tee -a "$EVID/02_stat.txt"
    /usr/bin/find "$d" -maxdepth 3 -type f -print0 2>/dev/null \
      | xargs -0 -I{} /usr/bin/stat -f "%m %N" "{}" 2>/dev/null \
      | sort -nr | head -n 50 | tee -a "$EVID/02_stat.txt" || true
  else
    echo "--- $d (missing)" | tee -a "$EVID/02_stat.txt"
  fi
done

echo "== 3) Grep likely regen sources (scripts/commands/plists) ==" | tee "$EVID/03_grep_sources.txt"
patterns=(
  "mkdir -p artifacts"
  "mkdir -p .*artifacts"
  "/artifacts"
  "artifacts/"
  "mkdir -p logs"
  "/logs"
  "0luka/logs"
  "promote_artifact"
  "atg_multi_snap"
  "core_history"
  "heartbeat"
)

targets=(
  "$ROOT/.0luka"
  "$ROOT/ops"
  "$ROOT/runtime"
  "$HOME/Library/LaunchAgents"
  "$HOME/Library/LaunchDaemons"
)

for t in "${targets[@]}"; do
  [[ -e "$t" ]] || continue
  echo "--- TARGET: $t" | tee -a "$EVID/03_grep_sources.txt"
  for p in "${patterns[@]}"; do
    /usr/bin/grep -RIn --exclude-dir='.git' --exclude='*.png' --exclude='*.jpg' --exclude='*.pdf' \
      "$p" "$t" 2>/dev/null | head -n 200 | sed "s|$HOME|~|g" | tee -a "$EVID/03_grep_sources.txt" || true
  done
done

echo "== 4) launchctl loaded jobs (filtered) ==" | tee "$EVID/04_launchctl.txt"
launchctl list | grep -Ei '(0luka|02luka|opal|mary|dispatcher|shell|watcher|clc|bridge|atg)' \
  | tee -a "$EVID/04_launchctl.txt" || true

echo "== 5) Recent root-level file creations (git status + untracked) ==" | tee "$EVID/05_git_status.txt"
git -C "$ROOT" status --porcelain | tee -a "$EVID/05_git_status.txt" || true

# Copy zen evidence if exists
if [[ -f "$ROOT/observability/artifacts/zen_claim_260124_065241_30b935e7a01d37fe.json" ]]; then
  cp -a "$ROOT/observability/artifacts/zen_claim_260124_065241_30b935e7a01d37fe.json" "$EVID/"
  shasum -a 256 "$EVID/zen_claim_260124_065241_30b935e7a01d37fe.json" | tee -a "$EVID/00_context.txt"
fi

echo
echo "DONE. Evidence bundle:"
echo "$EVID"
