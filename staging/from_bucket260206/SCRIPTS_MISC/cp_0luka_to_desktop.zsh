#!/usr/bin/env zsh
set -euo pipefail

SRC="${HOME}/0luka"
DESK="${HOME}/Desktop"
TS="$(date +%Y%m%d_%H%M%S)"
DST="${DESK}/0luka_${TS}"

if [[ ! -d "$SRC" ]]; then
  echo "❌ Source not found: $SRC"
  exit 1
fi

mkdir -p "$DST"

# Copy with exclusions (safe + fast)
rsync -a --delete \
  --exclude ".git/" \
  --exclude ".env*" \
  --exclude ".gemini/" \
  --exclude "runtime/" \
  --exclude "logs/" \
  --exclude "g/logs/" \
  --exclude "observability/logs/" \
  --exclude "interface/evidence/" \
  --exclude "interface/state/" \
  --exclude "interface/inflight/" \
  --exclude "interface/processing/" \
  --exclude "interface/pending/" \
  --exclude "interface/pending_approval/" \
  --exclude "interface/rejected/" \
  "$SRC/" "$DST/"

# Basic manifest for audit (no hashing huge trees)
{
  echo "snapshot_ts=${TS}"
  echo "src=${SRC}"
  echo "dst=${DST}"
  echo "uname=$(uname -a)"
  echo "git_head=$(git -C "$SRC" rev-parse HEAD 2>/dev/null || echo 'NO_GIT')"
} > "${DST}/COPY_MANIFEST.txt"

echo "✅ Copied to: $DST"
echo "📄 Manifest:  ${DST}/COPY_MANIFEST.txt"
