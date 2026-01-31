#!/usr/bin/env zsh
set -euo pipefail

# tools/external/export_bundle.zsh
# Exports public contract artifacts to artifacts/public_bundle_<ts>.zip

HERE="$(cd "$(dirname "$0")" && pwd -P)"
ROOT="$(cd "$HERE/../../" && pwd -P)"

DEST_DIR="$ROOT/artifacts/public_bundle"
mkdir -p "$DEST_DIR"

TS="$(date -u +"%Y%m%dT%H%M%SZ")"
ZIP_NAME="public_bundle_${TS}.zip"
ZIP_PATH="$ROOT/artifacts/${ZIP_NAME}"

# Source Artifacts
PROGRESS_MD="$ROOT/observability/dashboard/progress/latest.md"
PROGRESS_JSON="$ROOT/observability/dashboard/progress/latest.json"
SUMMARY_MD="$ROOT/reports/summary/latest.md"

if [[ ! -f "$PROGRESS_MD" ]]; then echo "Missing: $PROGRESS_MD"; exit 1; fi
if [[ ! -f "$PROGRESS_JSON" ]]; then echo "Missing: $PROGRESS_JSON"; exit 1; fi
if [[ ! -f "$SUMMARY_MD" ]]; then echo "Missing: $SUMMARY_MD"; exit 1; fi

# Staging
cp "$PROGRESS_MD" "$DEST_DIR/dashboard_latest.md"
cp "$PROGRESS_JSON" "$DEST_DIR/dashboard_latest.json"
cp "$SUMMARY_MD" "$DEST_DIR/summary_latest.md"

# Zip
cd "$ROOT/artifacts"
zip -q -r "$ZIP_NAME" "public_bundle"

# Checksum
HASH="$(shasum -a 256 "$ZIP_NAME" | awk '{print $1}')"

# Output JSON
cat <<JSON
{
  "ts_utc": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "zip_path": "$ZIP_PATH",
  "sha256": "$HASH",
  "contents": [
    "dashboard_latest.md",
    "dashboard_latest.json",
    "summary_latest.md"
  ]
}
JSON
