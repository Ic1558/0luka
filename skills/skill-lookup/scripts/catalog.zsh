#!/bin/zsh
# skill-lookup/scripts/catalog.zsh

SKILLS_DIR="skills"
SEARCH_TERM=$2

if [[ "$1" == "--find" && -n "$SEARCH_TERM" ]]; then
  echo "🔍 Searching for '$SEARCH_TERM' in skills..."
  grep -r "$SEARCH_TERM" $SKILLS_DIR/**/SKILL.md | cut -d: -f1 | sort | uniq
else
  echo "📚 Skill Catalog:"
  echo "-----------------"
  for d in $SKILLS_DIR/*; do
    if [[ -d "$d" ]]; then
      SKILL_NAME=$(basename "$d")
      if [[ -f "$d/SKILL.md" ]]; then
        # Check if SOT compliant (lazy check)
        IS_SOT=" "
        grep -q "sot: true" "$d/SKILL.md" && IS_SOT="✅"
        echo "$IS_SOT $SKILL_NAME"
      fi
    fi
  done
fi
