#!/usr/bin/env zsh
# wo_tag_phase12_4.zsh — Create and push "phase-12.4" tag.
# ARCHIVED: One-shot phase tagger.
set -euo pipefail
REPO="${HOME}/LocalProjects/02luka_local_g/g"
cd "$REPO"
TS="$(date +%y%m%d_%H%M)"
git fetch origin main; git checkout main; git pull
TAG="phase-12.4"
MSG="Phase 12.4: DevContainer Auto-Workspace + Docs Update (${TS})"
echo "🏷️  Creating tag $TAG ..."
git tag -a "$TAG" -m "$MSG"
git push origin "$TAG"
echo "✅  Tag $TAG pushed successfully."
