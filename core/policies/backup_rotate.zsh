#!/usr/bin/env zsh
set -euo pipefail
f="$1"
[[ -f "$f" ]] || exit 0
ts="$(date +%y%m%d_%H%M%S)"
cp -a "$f" "$f.bak.$ts"
b=( ${(On)$(ls -1 "$f".bak.* 2>/dev/null || true)} )
(( ${#b[@]} > 2 )) && rm -f -- "${b[@]:2}"
