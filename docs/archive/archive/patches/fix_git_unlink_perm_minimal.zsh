#!/usr/bin/env zsh
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# Tracked modified files that must be reverted (from your status)
NEED_REVERT=(
  core_brain/governance/agents.md
  core_brain/governance/router.md
  core_brain/ops/core_kernel/router.py
  core_brain/ops/governance/foundation_decommission.sh
  core_brain/ops/governance/gate_runner.py
  core_brain/ops/governance/gate_runnerd.py
  core_brain/ops/governance/gate_runnerd_v050.py
  core_brain/ops/governance/handlers/legacy_withdraw.zsh
  core_brain/ops/governance/zen_audit.sh
  core_brain/ops/tools/wo_audit_root_regen_v1.zsh
)

echo "ROOT=$ROOT"
echo
echo "== A) Show dir permissions (parents matter for unlink) =="
for f in "${NEED_REVERT[@]}"; do
  d="$(dirname "$f")"
  echo "--- $d"
  ls -ldO@ "$d" || true
done

echo
echo "== B) Grant user write on those directories (minimal) =="
# NOTE: unlink requires write+execute on the directory, not just the file.
for f in "${NEED_REVERT[@]}"; do
  d="$(dirname "$f")"
  chmod u+w "$d" 2>/dev/null || sudo chmod u+w "$d"
done

echo
echo "== C) Ensure the files themselves are writable by user (minimal) =="
for f in "${NEED_REVERT[@]}"; do
  [[ -e "$f" ]] || continue
  chmod u+w "$f" 2>/dev/null || sudo chmod u+w "$f"
done

echo
echo "== D) Retry revert ONLY these tracked files =="
git restore --staged --worktree -- "${NEED_REVERT[@]}"

echo
echo "== E) Status after revert attempt =="
git status --porcelain
