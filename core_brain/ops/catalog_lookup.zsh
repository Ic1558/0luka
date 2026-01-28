#!/bin/zsh
# 0luka Catalog Lookup Tool
# Usage: tools/catalog_lookup.zsh <tool-name>
# Returns: Absolute path to the tool if found in registry, else exit 1

set -euo pipefail

# Locate Registry
ROOT="${0:A:h:h:h}"
REGISTRY="$ROOT/core_brain/catalog/registry.yaml"

if [[ ! -f "$REGISTRY" ]]; then
    echo "ERROR: Registry not found at $REGISTRY" >&2
    exit 1
fi

TOOL_NAME="$1"
if [[ -z "$TOOL_NAME" ]]; then
    echo "Usage: $0 <tool-name>" >&2
    exit 1
fi

# Use python to parse yaml safely (no yq dependency required if python is standard)
RESULT=$(python3 -c "
import sys, yaml
try:
    with open('$REGISTRY', 'r') as f:
        data = yaml.safe_load(f)
    
    tools = data.get('tools', [])
    found = next((t for t in tools if t['name'] == '$TOOL_NAME'), None)
    
    if found:
        print(found['path'])
    else:
        sys.exit(1)
except Exception as e:
    sys.exit(2)
")

EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
    # echo "Tool '$TOOL_NAME' not found in registry." >&2
    exit 1
fi

# Convert relative path in registry to absolute path
if [[ "$RESULT" = /* ]]; then
    echo "$RESULT"
else
    echo "$ROOT/$RESULT"
fi
