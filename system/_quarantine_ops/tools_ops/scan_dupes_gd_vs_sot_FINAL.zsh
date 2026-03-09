#!/usr/bin/env zsh
# scan_dupes_gd_vs_sot_FINAL.zsh — scan Google Drive vs SOT for orphans and name-clashes
# Usage:
#   SOT=/path/to/sot GD=/path/to/gd zsh tools/ops/scan_dupes_gd_vs_sot_FINAL.zsh
#   MAX_DEPTH=4 zsh tools/ops/scan_dupes_gd_vs_sot_FINAL.zsh
# Outputs: reports/dupes_report_<stamp>.md + .csv
set -euo pipefail

SOT="${SOT:-$HOME/LocalProjects/02luka_local_g}"
GD="${GD:-$HOME/gd/02luka}"
OUT_DIR="$SOT/g/reports/scan_temp"; mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
REPORT_MD="$SOT/g/reports/dupes_report_${STAMP}.md"
REPORT_CSV="$SOT/g/reports/dupes_report_${STAMP}.csv"
MAX_DEPTH="${MAX_DEPTH:-6}"

echo "# GD vs SOT duplicate/orphan scan @ ${STAMP}" > "$REPORT_MD"
echo "scope,relpath,size,mtime" > "$REPORT_CSV"

have_gfind=0
command -v gfind >/dev/null 2>&1 && have_gfind=1

prune_args=(
  -not -path "*/.git/*"
  -not -path "*/node_modules/*"
  -not -path "*/venv/*"
  -not -path "*/.legacy*/*"
  -not -path "*/.Trash/*"
  -not -path "*/@eaDir/*"
  -not -path "*/*.photoslibrary/*"
)

if [[ "$have_gfind" == 1 ]]; then
  gfind "$SOT" -xdev -maxdepth "$MAX_DEPTH" -type f "${prune_args[@]}" \
    -printf "SOT,%P,%s,%T@\n" >> "$REPORT_CSV"
  gfind "$GD" -xdev -maxdepth "$MAX_DEPTH" -type f "${prune_args[@]}" \
    -printf "GD,%P,%s,%T@\n"  >> "$REPORT_CSV"
else
  find_list_bsd() {
    local root="$1"; local scope="$2"
    find "$root" -type f -maxdepth "$MAX_DEPTH" \
      -not -path "*/.git/*" -not -path "*/node_modules/*" \
      -not -path "*/venv/*" -not -path "*/.legacy*/*" \
      -not -path "*/.Trash/*" -not -path "*/@eaDir/*" \
      -not -path "*/*.photoslibrary/*" \
      -exec sh -c '
        root="$1"; shift
        for f in "$@"; do
          rp="${f#${root}/}"
          sz=$(stat -f "%z" "$f" 2>/dev/null || echo 0)
          mt=$(stat -f "%m" "$f" 2>/dev/null || echo 0)
          printf "%s,%s,%s,%s\n" "'"$scope"'" "$rp" "$sz" "$mt"
        done
      ' _ "$root" {} +
  }
  find_list_bsd "$SOT" "SOT" >> "$REPORT_CSV"
  find_list_bsd "$GD"  "GD"  >> "$REPORT_CSV"
fi

awk -F',' '$1=="SOT"{print $2}' "$REPORT_CSV" | sort -u > "$OUT_DIR/sot_rel.list"
awk -F',' '$1=="GD"{print  $2}' "$REPORT_CSV" | sort -u > "$OUT_DIR/gd_rel.list"

{
  echo ""
  echo "## ORPHANS in GD (not in SOT)"
  comm -13 "$OUT_DIR/sot_rel.list" "$OUT_DIR/gd_rel.list" | while read -r REL; do
    SZ=$(awk -F',' -v r="$REL" '$1=="GD" && $2==r{print $3; exit}' "$REPORT_CSV")
    MT=$(awk -F',' -v r="$REL" '$1=="GD" && $2==r{print $4; exit}' "$REPORT_CSV")
    echo "- $REL (size=$SZ, mtime=$MT)"
  done
} >> "$REPORT_MD"

{
  echo ""
  echo "## NAME CLASH (same relpath, different size)"
  join -t$'\t' -j 1 \
    <(awk -F',' '$1=="SOT"{print $2"\t"$3}' "$REPORT_CSV" | sort) \
    <(awk -F',' '$1=="GD"{print  $2"\t"$3}' "$REPORT_CSV" | sort) \
  | awk -F'\t' '$2!=$3{print "- "$1" (SOT:"$2", GD:"$3")"}'
} >> "$REPORT_MD"

echo ""
echo "[OK] Reports written:"
echo "  $REPORT_MD"
echo "  $REPORT_CSV"
