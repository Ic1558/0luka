#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT"

ALLOWLIST_FILE="core/activity_feed_guard.py"
TMP_HITS="$(mktemp /tmp/feed_integrity_hits.XXXXXX)"
TMP_BAD="$(mktemp /tmp/feed_integrity_bad.XXXXXX)"
trap 'rm -f "$TMP_HITS" "$TMP_BAD"' EXIT

search_with_rg() {
  local -a excludes
  excludes=(
    --glob '!.git/**'
    --glob '!_scratch/**'
    --glob '!observability/**'
    --glob '!runtime/**'
    --glob '!reports/**'
    --glob '!docs/notebooklm/**'
    --glob '!node_modules/**'
    --glob '!dist/**'
    --glob '!build/**'
  )

  local -a includes
  includes=(
    --glob '*.sh' --glob '*.zsh' --glob '*.bash'
    --glob '*.py' --glob '*.pyi'
    --glob '*.js' --glob '*.mjs' --glob '*.cjs'
    --glob '*.ts' --glob '*.tsx'
    --glob '*.yaml' --glob '*.yml'
  )

  local -a roots
  roots=(tools modules interface core)

  : > "$TMP_HITS"

  rg -n --hidden --no-heading --no-messages "(>>|[^<]>|:\\s*>)\\s*[^#\\n]*activity_feed\\.jsonl" "${excludes[@]}" "${includes[@]}" "${roots[@]}" >> "$TMP_HITS" || true
  rg -n --hidden --no-heading --no-messages "\\b(cp|mv|rsync)\\b[^\\n]*activity_feed\\.jsonl" "${excludes[@]}" "${includes[@]}" "${roots[@]}" >> "$TMP_HITS" || true
  rg -n --hidden --no-heading --no-messages "open\\([^\\n)]*activity_feed\\.jsonl[^\\n)]*,\\s*['\"][wa]['\"]" "${excludes[@]}" "${includes[@]}" "${roots[@]}" >> "$TMP_HITS" || true
  rg -n --hidden --no-heading --no-messages "Path\\([^\\n)]*activity_feed\\.jsonl[^\\n)]*\\)\\.(write_text|write_bytes)\\s*\\(" "${excludes[@]}" "${includes[@]}" "${roots[@]}" >> "$TMP_HITS" || true
}

search_with_grep() {
  : > "$TMP_HITS"
  local -a roots
  roots=(tools modules interface core)

  local -a grep_common
  grep_common=(
    --exclude-dir=.git
    --exclude-dir=_scratch
    --exclude-dir=observability
    --exclude-dir=runtime
    --exclude-dir=reports
    --exclude-dir=node_modules
    --exclude-dir=dist
    --exclude-dir=build
    --exclude-dir=docs/notebooklm
    --include='*.sh' --include='*.zsh' --include='*.bash'
    --include='*.py' --include='*.pyi'
    --include='*.js' --include='*.mjs' --include='*.cjs'
    --include='*.ts' --include='*.tsx'
    --include='*.yaml' --include='*.yml'
  )

  grep -RInE "(>>|[^<]>|:\\s*>)\\s*[^#\\n]*activity_feed\\.jsonl" "${grep_common[@]}" "${roots[@]}" >> "$TMP_HITS" || true
  grep -RInE "\\b(cp|mv|rsync)\\b[^\\n]*activity_feed\\.jsonl" "${grep_common[@]}" "${roots[@]}" >> "$TMP_HITS" || true
  grep -RInE "open\\([^\\n)]*activity_feed\\.jsonl[^\\n)]*,\\s*['\"][wa]['\"]" "${grep_common[@]}" "${roots[@]}" >> "$TMP_HITS" || true
  grep -RInE "Path\\([^\\n)]*activity_feed\\.jsonl[^\\n)]*\\)\\.(write_text|write_bytes)\\s*\\(" "${grep_common[@]}" "${roots[@]}" >> "$TMP_HITS" || true
}

if command -v rg >/dev/null 2>&1; then
  search_with_rg
elif command -v grep >/dev/null 2>&1; then
  search_with_grep
else
  echo "FEED_INTEGRITY_GATE: TOOL_ERROR"
  exit 2
fi

sort -u "$TMP_HITS" -o "$TMP_HITS"
: > "$TMP_BAD"

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  file="${line%%:*}"
  file="${file#./}"
  if [[ "$file" != "$ALLOWLIST_FILE" ]]; then
    print -r -- "$line" >> "$TMP_BAD"
  fi
done < "$TMP_HITS"

if [[ -s "$TMP_BAD" ]]; then
  echo "FEED_INTEGRITY_GATE: FAIL"
  cat "$TMP_BAD"
  exit 1
fi

echo "FEED_INTEGRITY_GATE: PASS"
exit 0
