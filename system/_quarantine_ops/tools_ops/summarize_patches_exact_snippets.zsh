#!/usr/bin/env zsh
# summarize_patches_exact_snippets.zsh — generate markdown summary of exact diff snippets
# Usage: zsh tools/ops/summarize_patches_exact_snippets.zsh [ROOT] [PATCH_DIR] [OUT_FILE]
#   ROOT       — project root (default: $PWD)
#   PATCH_DIR  — dir containing *.patch files (default: ROOT/artifacts/archive)
#   OUT_FILE   — output path (default: ROOT/artifacts/public_bundle/patch_snippets_<stamp>.md)
set -euo pipefail

ROOT="${1:-$PWD}"
PATCH_DIR="${2:-$ROOT/artifacts/archive}"

if [[ ! -d "$PATCH_DIR" ]]; then
  echo "ERROR: patch dir not found: $PATCH_DIR" >&2
  exit 1
fi

out="${3:-$ROOT/artifacts/public_bundle/patch_snippets_$(date -u +%Y%m%dT%H%M%SZ).md}"
mkdir -p "$(dirname "$out")"

print_md_header() {
  cat <<EOF
# Patch Snippets (Exact)
Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Patch dir: $PATCH_DIR

EOF
}

extract_patch() {
  local p="$1"
  echo "## $(basename "$p")"
  echo
  echo "**Files:**"
  awk '/^\+\+\+ /{print "- " $2}' "$p" | sed 's/^b\///' | sort -u
  echo

  awk '
  function flush_hunk() {
    if (!in_hunk) return
    for (i=1;i<=n;i++) keep[i]=0
    for (i=1;i<=n;i++) {
      if (substr(L[i],1,1)=="+" || substr(L[i],1,1)=="-") {
        keep[i]=1
        for (j=i-ctx;j<=i+ctx;j++) if (j>=1 && j<=n) keep[j]=1
      }
    }
    has=0
    for (i=1;i<=n;i++) if (keep[i]) {has=1; break}
    if (!has) { in_hunk=0; n=0; return }

    print "```diff"
    if (cur_old!="") print cur_old
    if (cur_new!="") print cur_new
    print hhdr
    for (i=1;i<=n;i++) if (keep[i]) print L[i]
    print "```"
    print ""
    in_hunk=0; n=0
  }

  BEGIN {ctx=6; cur_old=""; cur_new=""; in_hunk=0; n=0; hhdr=""}
  /^--- / {flush_hunk(); cur_old=$0; next}
  /^\+\+\+ / {flush_hunk(); cur_new=$0; next}
  /^@@ / {
    flush_hunk()
    in_hunk=1
    hhdr=$0
    n=0
    next
  }
  {
    if (in_hunk) { n++; L[n]=$0 }
  }
  END {flush_hunk()}
  ' "$p"
}

{
  print_md_header
  found=0
  for p in "$PATCH_DIR"/*.patch(.N); do
    extract_patch "$p"
    found=1
  done
  if [[ $found -eq 0 ]]; then
    echo "_No .patch files found in $PATCH_DIR_"
  fi
} > "$out"

echo "OK: wrote $out"
ls -lh "$out"
