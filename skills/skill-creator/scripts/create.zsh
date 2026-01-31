#!/bin/zsh
# skill-creator/scripts/create.zsh
# Usage: create.zsh <skill_name> "<short_description>"

SKILL_NAME=$1
DESCRIPTION=$2
TEMPLATE_FILE="skills/SOT_TEMPLATE.md"
TARGET_DIR="skills/$SKILL_NAME"

if [[ -z "$SKILL_NAME" ]]; then
  echo "Usage: $0 <skill_name> [description]"
  exit 1
fi

if [[ -d "$TARGET_DIR" ]]; then
  echo "Error: Skill '$SKILL_NAME' already exists."
  exit 1
fi

echo "Creating skill: $SKILL_NAME..."

# 1. Structure
mkdir -p "$TARGET_DIR/scripts"
mkdir -p "$TARGET_DIR/references"
mkdir -p "$TARGET_DIR/assets"

# 2. SKILL.md
if [[ -f "$TEMPLATE_FILE" ]]; then
  # Basic replacement (rudimentary, can be improved)
  sed "s/name: .*/name: $SKILL_NAME/" "$TEMPLATE_FILE" > "$TARGET_DIR/SKILL.md"
  
  # Inject description if possible (sed is tricky with multiline, just doing basic meta)
  echo "--> Initialized $TARGET_DIR/SKILL.md from template."
else
  echo "Warning: Template $TEMPLATE_FILE not found. Creating blank SKILL.md."
  echo "# Skill: $SKILL_NAME\n\n---" > "$TARGET_DIR/SKILL.md"
fi

# 3. Validation
if [[ -f "$TARGET_DIR/SKILL.md" ]]; then
  echo "✅ Skill '$SKILL_NAME' created successfully at $TARGET_DIR"
else
  echo "❌ Failed to create SKILL.md"
  exit 1
fi
