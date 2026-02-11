#!/usr/bin/env zsh
set -euo pipefail
IFS=$'\n\t'

CODEX="$HOME/0luka/skills/codex/codex.zsh"
[[ -f "$CODEX" ]] || { print -r -- "ERR: missing $CODEX"; exit 2; }

perl -0777 -i -pe '
  # Inject GREP resolver near top (after VERSION is fine)
  s/(VERSION="0\.1\.0"\n)/$1\n# Resolve grep (PATH may be restricted under venv or strict headers)\nGREP_BIN="${GREP_BIN:-$(command -v grep 2>\\/dev\\/null || true)}"\nif [[ -z "${GREP_BIN}" && -x "\\/usr\\/bin\\/grep" ]]; then\n  GREP_BIN="\\/usr\\/bin\\/grep"\nfi\nif [[ -z "${GREP_BIN}" ]]; then\n  log_err "missing dependency: grep (not found on PATH)";\n  exit 127\nfi\n\n/;

  # Replace grep invocation with ${GREP_BIN}
  s/\\bg?rep -RIn --/\\${GREP_BIN} -RIn --/g;
' "$CODEX"

chmod +x "$CODEX"
print -r -- "OK: patched grep resolution in $CODEX"
