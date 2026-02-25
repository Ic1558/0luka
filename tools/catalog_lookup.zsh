#!/bin/zsh
# tools/catalog_lookup.zsh
# Wrapper for core catalog lookup. No hardcoded paths.

ROOT="${0:A:h:h}"
CATALOG_TOOL="$ROOT/core_brain/ops/catalog_lookup.zsh"

if [[ -f "$CATALOG_TOOL" ]]; then
    zsh "$CATALOG_TOOL" "$@"
else
    echo "ERROR: Core catalog lookup tool not found at $CATALOG_TOOL" >&2
    exit 1
fi
