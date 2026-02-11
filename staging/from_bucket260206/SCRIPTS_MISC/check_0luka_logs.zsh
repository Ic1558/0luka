#!/usr/bin/env zsh
set -euo pipefail

# --- configure root candidates ---
CANDIDATES=(
  "$HOME/0luka"
  "$HOME/00luka"
  "$HOME/01luka"
  "$HOME/02luka"
  "$HOME/LocalProjects/0luka"
  "$HOME/LocalProjects/02luka_local_g"
)

TARGETS=(bridge_consumer clc_local followup_generator lac)

print "\n=== 0luka presence & current.log check ==="
print "Time: $(date -Is)"
print "User: $(whoami)"
print ""

# pick best root
ROOT=""
for d in "${CANDIDATES[@]}"; do
  if [[ -d "$d" ]]; then
    ROOT="$d"
    break
  fi
done

if [[ -z "$ROOT" ]]; then
  print "❌ No root found in candidates:"
  printf "  - %s\n" "${CANDIDATES[@]}"
  exit 1
fi

print "✅ Using root: $ROOT\n"

# helper: show file info
_show_file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    print "  ✅ file: $f"
    print "     size: $(stat -f %z "$f" 2>/dev/null || wc -c <"$f") bytes"
    print "     mtime: $(stat -f %Sm -t '%Y-%m-%d %H:%M:%S' "$f" 2>/dev/null || date -r "$f" '+%Y-%m-%d %H:%M:%S')"
  else
    print "  ❌ missing: $f"
  fi
}

# 1) search for directories named targets (fast-ish)
print "== 1) Directory presence (top 6 levels) =="
for t in "${TARGETS[@]}"; do
  print "\n-- $t --"
  # find directories named exactly target within root (limit depth)
  matches=("${(@f)$(find "$ROOT" -maxdepth 6 -type d -name "$t" 2>/dev/null | head -n 20)}")
  if (( ${#matches[@]} == 0 )); then
    print "  ❌ no dir named '$t' within $ROOT (maxdepth 6)"
  else
    print "  ✅ found dirs:"
    printf "  - %s\n" "${matches[@]}"
    # check current.log near each match
    for m in "${matches[@]}"; do
      _show_file "$m/current.log"
      _show_file "$m/logs/current.log"
    done
  fi
done

# 2) search current.log occurrences
print "\n== 2) Any current.log mentioning these targets (filename search) =="
for t in "${TARGETS[@]}"; do
  print "\n-- current.log near '$t' --"
  logs=("${(@f)$(find "$ROOT" -maxdepth 8 -type f -name "current.log" 2>/dev/null | grep -i "$t" | head -n 20)}")
  if (( ${#logs[@]} == 0 )); then
    print "  ❌ no current.log paths matching '$t' within $ROOT (maxdepth 8)"
  else
    print "  ✅ found:"
    printf "  - %s\n" "${logs[@]}"
  fi
done

# 3) process check (best-effort)
print "\n== 3) Process hints (ps grep) =="
for t in "${TARGETS[@]}"; do
  print "\n-- ps for $t --"
  ps aux | grep -i "$t" | grep -v grep | head -n 20 || true
done

# 4) launchd check (if you use it)
print "\n== 4) launchd hints (list | grep) =="
for t in "${TARGETS[@]}"; do
  print "\n-- launchctl for $t --"
  launchctl list 2>/dev/null | grep -i "$t" | head -n 20 || true
done

print "\n=== Done ==="
