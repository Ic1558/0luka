#!/usr/bin/env zsh
set -uo pipefail

ROOT="${1:-${ROOT:-$HOME/0luka}}"
ROOT="${ROOT%/}"
ROOT_REF='${ROOT}'
normalize_paths() { sed "s|$ROOT|$ROOT_REF|g"; }
OUTDIR="$ROOT/observability/audit"
mkdir -p "$OUTDIR"

STAMP="$(date +%y%m%d_%H%M%S)"
OUT="$OUTDIR/${STAMP}_judicial_reality_audit.md"

{
  echo "# Judicial Reality Audit (Final Mile)"
  echo
  echo "- Generated: $(date)"
  echo "- Root: $ROOT"
  echo

  echo "## 1) Socket Identity Check"
  echo "- Checking for getpeereid() usage in daemon"
  echo '```text'
  grep -r "getpeereid" "$ROOT/ops/governance/gate_runnerd.py" || echo "FAIL: No getpeereid check found"
  echo '```'
  echo

  echo "## 2) Protocol Framing Check"
  echo "- Checking for struct.pack('>I'...) usage (Length Prefix)"
  echo '```text'
  grep -r "struct.pack" "$ROOT/ops/governance/gate_runnerd.py" || echo "FAIL: No struct.pack found in daemon"
  grep -r "struct.pack" "$ROOT/ops/governance/rpc_client.py" || echo "FAIL: No struct.pack found in client"
  echo '```'
  echo "- Checking for unsafe recv(4096) without loop/framing"
  echo '```text'
  # We expect recv(4) for length, then loop.
  grep -r "recv(4096)" "$ROOT/ops/governance/gate_runnerd.py" | grep -v "min(4096" || echo "OK: No naked recv(4096) found (checked min usage)"
  echo '```'
  echo

  echo "## 3) Global Beacon"
  echo "- Checking existence of global_beacon.jsonl"
  if [[ -f "$ROOT/observability/stl/ledger/global_beacon.jsonl" ]]; then
     echo "OK: Beacon exists"
     tail -n 3 "$ROOT/observability/stl/ledger/global_beacon.jsonl"
  else
     echo "FAIL: Beacon missing"
  fi
  echo

  echo "## 4) Ontology Seal"
  echo "- Checking for ontology seal logic in daemon"
  grep "seal_ontology" "$ROOT/ops/governance/gate_runnerd.py" || echo "FAIL: No seal_ontology method"
  echo

  echo "## 5) Action Purity"
  echo "- Checking ACTION_TABLE"
  grep "ACTION_TABLE =" "$ROOT/ops/governance/gate_runnerd.py" || echo "FAIL: No ACTION_TABLE"
  echo

  echo "## 6) Temporal Purity"
  echo "- Checking for datetime usage in judicial critical paths"
  grep "datetime" "$ROOT/ops/governance/gate_runnerd.py" || echo "OK: No datetime in daemon"
  echo

} > "$OUT"

echo "✅ Wrote audit report:"
echo "$OUT" | normalize_paths
cat "$OUT" | normalize_paths
