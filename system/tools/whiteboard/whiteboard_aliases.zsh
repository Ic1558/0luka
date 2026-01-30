#!/usr/bin/env zsh
# 0luka Whiteboard v1 aliases
# Usage: source system/tools/whiteboard/whiteboard_aliases.zsh

LUKA_BASE="${LUKA_BASE:-$HOME/0luka}"

print() {
  if [[ $# -eq 0 ]]; then
    echo "=== 0luka Whiteboard Summary ==="
    "$LUKA_BASE/tools/whiteboard_print.zsh" liam || true
    echo
    "$LUKA_BASE/tools/whiteboard_print.zsh" lisa || true
    echo
    "$LUKA_BASE/tools/whiteboard_print.zsh" codex || true
  else
    zsh "$LUKA_BASE/tools/whiteboard_print.zsh" "$@"
  fi
  fi
}

alias last_action="cat $LUKA_BASE/observability/whiteboard/pointers/last_action.txt"
alias last_snapshot="cat $LUKA_BASE/observability/whiteboard/pointers/last_snapshot.txt"
