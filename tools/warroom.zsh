#!/bin/zsh
# tools/warroom.zsh
# Compatibility wrapper for decision_box.zsh. No hardcoded paths.

ROOT="${0:A:h:h}"
DECISION_TOOL="$ROOT/tools/ops/decision_box.zsh"

if [[ -f "$DECISION_TOOL" ]]; then
    # Proxy all arguments to decision_box
    # Note: decision_box uses --title, --why etc. 
    # If the legacy warroom used positional args, we'd need more logic here.
    # But based on the user's request, they are already using --fill which implies decision_box logic.
    zsh "$DECISION_TOOL" "$@"
else
    echo "ERROR: Decision box tool not found at $DECISION_TOOL" >&2
    exit 1
fi
