#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"

target="${ROOT}/tools/bridge_task_emit.zsh"

if (( $# == 0 )); then
  exit 0
fi

if [[ ! -f "${target}" ]]; then
  print -r -- "[ERR ] bridge_task_emit.zsh not found: ${target}" >&2
  exit 1
fi

/bin/zsh "${target}" "$@"
