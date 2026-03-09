#!/usr/bin/env zsh
# scan_pending_no_result.zsh — scan interface queue for pending tasks with no completion signal
# Usage: ROOT=/path/to/interface zsh tools/ops/scan_pending_no_result.zsh
# Scans: inbox/ inflight/ pending/ vs done/ outbox/ evidence/
set -euo pipefail

ROOT="${ROOT:-/Users/icmini/0luka/interface}"

echo "== Scan: inbox/inflight/pending vs done/outbox/evidence =="
echo "ROOT=$ROOT"
echo

extract_ids() {
  sed -E 's/.*(task_[0-9]{8}_[0-9]{6}_[a-z0-9]+).*/\1/i' \
  | sed -E 's/.*(TASK-[A-Z0-9_-]+).*/\1/i'
}

tmp="$(mktemp)"
{
  find "$ROOT/inbox"   -type f 2>/dev/null || true
  find "$ROOT/inflight" -type f 2>/dev/null || true
  find "$ROOT/pending" -type f 2>/dev/null || true
} | sort > "$tmp"

echo "-- Candidates (inbox/inflight/pending): $(wc -l < "$tmp") files"

done_tmp="$(mktemp)"
{
  find "$ROOT/done"     -type f 2>/dev/null || true
  find "$ROOT/outbox"   -type f 2>/dev/null || true
  find "$ROOT/evidence" -type f 2>/dev/null || true
} | sort > "$done_tmp"

echo "-- Completion signals (done/outbox/evidence): $(wc -l < "$done_tmp") files"
echo

echo "== Likely pending tasks (no matching name token in done/outbox/evidence) =="

while IFS= read -r f; do
  b="$(basename "$f")"
  token=""
  if [[ "$b" =~ (task_[0-9]{8}_[0-9]{6}_[a-z0-9]+) ]]; then
    token="${match[1]}"
  elif [[ "$b" =~ (TASK-[A-Z0-9_-]+) ]]; then
    token="${match[1]}"
  else
    continue
  fi
  if ! grep -qi "$token" "$done_tmp"; then
    echo "PENDING_NO_RESULT  token=$token  file=$f"
  fi
done < "$tmp"

echo
echo "== Count by folder =="
for d in inbox inflight pending done outbox rejected evidence pending_approval processing; do
  p="$ROOT/$d"
  if [[ -d "$p" ]]; then
    c="$(find "$p" -type f 2>/dev/null | wc -l | tr -d ' ')"
    echo "$d: $c"
  fi
done

rm -f "$tmp" "$done_tmp"
