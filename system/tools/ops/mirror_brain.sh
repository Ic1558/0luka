#!/bin/zsh
# Mirror Antigravity Brain to SOT Artifacts
# Usage: ./mirror_brain.sh [conversation_id]

# Auto-detect logic
export CONVERSATION_ID="${1:-$GG_CONVERSATION_ID}"

if [[ -z "$CONVERSATION_ID" ]]; then
  BRAIN_ROOT="$HOME/.gemini/antigravity/brain"
  # Find latest by mtime
  LATEST=$(ls -td "$BRAIN_ROOT"/*/ 2>/dev/null | head -n 1 | xargs basename)
  if [[ -n "$LATEST" ]]; then
    echo "🔍 Auto-detected latest brain: $LATEST"
    CONVERSATION_ID="$LATEST"
  else
    echo "Error: No CONVERSATION_ID provided and none found in $BRAIN_ROOT"
    echo "Usage: ./mirror_brain.sh [conversation_id]"
    exit 1
  fi
fi

BRAIN_PATH="$HOME/.gemini/antigravity/brain/$CONVERSATION_ID"
SOT_MIRROR_PATH="$HOME/0luka/artifacts/antigravity/$CONVERSATION_ID"

if [[ ! -d "$BRAIN_PATH" ]]; then
  echo "Error: Brain path not found: $BRAIN_PATH"
  exit 1
fi

echo "Mirroring Brain -> SOT..."
echo "Src: $BRAIN_PATH"
echo "Dst: $SOT_MIRROR_PATH"

mkdir -p "$SOT_MIRROR_PATH"
cp -R "$BRAIN_PATH/" "$SOT_MIRROR_PATH/"

echo "✅ Mirror Complete."
ls -l "$SOT_MIRROR_PATH"
