#!/usr/bin/env zsh
set -e

echo "🔍 Antigravity → 02luka citizen linker (v2)"
echo "------------------------------------------"

# 1) Base paths
LAC_ROOT="${LAC_ROOT:-$HOME/LocalProjects/02luka_local_g}"
G_SRC="$LAC_ROOT/g/src"
TARGET_LINK="$G_SRC/antigravity"

echo "✅ Using 02luka root: $LAC_ROOT"
echo "✅ g/src path:       $G_SRC"
echo

# 2) Candidate sources (priority order)
CANDIDATES=(
  "$HOME/02luka/system/antigravity"
  "$HOME/.antigravity/antigravity"
  "$HOME/Library/Application Support/Antigravity"
  "$HOME/.gemini/antigravity"
)

FOUND_DIR=""

# 2.1 If ANTIGRAVITY_PATH is set & valid → use it
if [[ -n "$ANTIGRAVITY_PATH" && -d "$ANTIGRAVITY_PATH" ]]; then
  FOUND_DIR="$ANTIGRAVITY_PATH"
  echo "✅ Using ANTIGRAVITY_PATH from env:"
  echo "   $FOUND_DIR"
  echo
else
  # 2.2 Try known candidates
  echo "🔎 Searching for Antigravity directory..."
  for cand in $CANDIDATES; do
    if [[ -d "$cand" ]]; then
      FOUND_DIR="$cand"
      echo "   ✅ Found candidate: $FOUND_DIR"
      break
    fi
  done

  # 2.3 Last resort: global search (shallow)
  if [[ -z "$FOUND_DIR" ]]; then
    echo "   ℹ️ No candidate matched, doing shallow search (~, depth 4)..."
    FOUND_DIR="$(find "$HOME" -maxdepth 4 -type d -iname "antigravity" 2>/dev/null | head -n1)"
    if [[ -n "$FOUND_DIR" ]]; then
      echo "   ✅ Found via search: $FOUND_DIR"
    fi
  fi
fi

# 2.4 If still nothing → abort
if [[ -z "$FOUND_DIR" ]]; then
  echo "❌ ERROR: Could not find any Antigravity directory automatically."
  echo "   Please set ANTIGRAVITY_PATH and rerun, e.g.:"
  echo "     ANTIGRAVITY_PATH=\"/path/to/Antigravity\" ~/auto_link_antigravity.zsh"
  exit 1
fi

# 3) Prepare g/src
mkdir -p "$G_SRC"

# 4) If existing link/dir → show and confirm replace
if [[ -L "$TARGET_LINK" || -d "$TARGET_LINK" ]]; then
  echo "⚠️ Existing path at:"
  echo "   $TARGET_LINK"
  echo "   (type: $(test -L "$TARGET_LINK" && echo symlink || echo directory))"
  echo "   Removing and recreating..."
  rm -rf "$TARGET_LINK"
fi

# 5) Create symlink
ln -s "$FOUND_DIR" "$TARGET_LINK"

echo
echo "✅ Created symlink:"
echo "   $TARGET_LINK -> $FOUND_DIR"
echo

# 6) Verify
if [[ -L "$TARGET_LINK" ]]; then
  resolved="$(readlink "$TARGET_LINK")"
  echo "🔁 Verification:"
  ls -ld "$TARGET_LINK"
  echo "   points to: $resolved"
  echo
  echo "🎉 Done: Antigravity is now a citizen of 02luka."
  echo "   Allowed root path: g/src/antigravity"
  echo "   LAC/CLS can now write & run pipeline on this project."
  exit 0
else
  echo "❌ ERROR: Symlink creation appears to have failed."
  exit 1
fi
