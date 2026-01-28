#!/usr/bin/env zsh
# Git Safety Aliases - Source this in .zshrc
# Add to .zshrc: source ~/0luka/system/tools/git/git_aliases.zsh

ROOT="${ROOT:-${LUKA_SOT:-${HOME}/0luka}}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WARN_SCRIPT="${SCRIPT_DIR}/git_clean_warning.zsh"
SAFE_SCRIPT="${SCRIPT_DIR}/safe_git_clean.zsh"

# Override 'git clean' with warning
function git() {
  if [[ "$1" == "clean" && "$PWD" == *"/0luka"* ]]; then
    shift  # Remove 'clean' from args
    zsh "$WARN_SCRIPT" "$@"
  else
    command git "$@"
  fi
}

# Safe git clean aliases
alias git-safe-clean="zsh ${SAFE_SCRIPT} -n"
alias git-safe-clean-force="zsh ${SAFE_SCRIPT} -f"
