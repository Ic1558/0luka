#!/usr/bin/env zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK_SRC="$ROOT/.0luka/hooks"
HOOK_DST="$ROOT/.git/hooks"

die(){ print -r -- "ERROR: $*" >&2; exit 1; }
say(){ print -r -- "• $*"; }

[[ -d "$ROOT/.git" ]] || die "Not a git repo: $ROOT"
[[ -d "$HOOK_SRC" ]] || die "Missing hook source dir: $HOOK_SRC"

mkdir -p "$HOOK_DST"

for h in pre-commit pre-push; do
  [[ -f "$HOOK_SRC/$h" ]] || die "Missing hook: $HOOK_SRC/$h"
  cp -f "$HOOK_SRC/$h" "$HOOK_DST/$h"
  chmod +x "$HOOK_DST/$h"
  say "installed: .git/hooks/$h"
done

say "DONE. Hooks installed for this working copy."
