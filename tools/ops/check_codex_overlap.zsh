#!/usr/bin/env zsh
set -euo pipefail

CANONICAL_CODEX="/Applications/Codex.app/Contents/Resources/codex"

usage() {
  cat <<USAGE
Usage: tools/ops/check_codex_overlap.zsh [--sample-case ok|noncanonical|multi]

Checks for overlapping 'codex app-server' processes.
Exit codes:
  0 = exactly one canonical codex app-server and no non-canonical servers
  2 = canonical server count is invalid (zero or more than one)
  3 = non-canonical codex app-server detected
USAGE
}

collect_ps_lines() {
  local sample_case="${1:-}"
  case "$sample_case" in
    "")
      ps aux | rg -n "codex app-server" | rg -v "rg -n" || true
      ;;
    ok)
      cat <<SAMPLE
1:icmini 62443 0.0 0.2 435735792 32992 ?? S 12:42PM 0:19.44 ${CANONICAL_CODEX} app-server --analytics-default-enabled
SAMPLE
      ;;
    noncanonical)
      cat <<SAMPLE
1:icmini 62443 0.0 0.2 435735792 32992 ?? S 12:42PM 0:19.44 ${CANONICAL_CODEX} app-server --analytics-default-enabled
2:icmini 12574 0.0 0.1 435735792 12992 ?? S 12:42PM 0:03.11 /Users/icmini/.antigravity/extensions/openai.chatgpt-0.4.76-universal/bin/macos-aarch64/codex app-server --analytics-default-enabled
SAMPLE
      ;;
    multi)
      cat <<SAMPLE
1:icmini 62443 0.0 0.2 435735792 32992 ?? S 12:42PM 0:19.44 ${CANONICAL_CODEX} app-server --analytics-default-enabled
2:icmini 63421 0.0 0.2 435735792 32444 ?? S 12:45PM 0:02.01 ${CANONICAL_CODEX} app-server --analytics-default-enabled
SAMPLE
      ;;
    *)
      echo "ERROR: unknown sample case '$sample_case'" >&2
      usage >&2
      exit 64
      ;;
  esac
}

sample_case=""
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
if [[ "${1:-}" == "--sample-case" ]]; then
  if [[ -z "${2:-}" ]]; then
    echo "ERROR: --sample-case requires one of: ok, noncanonical, multi" >&2
    exit 64
  fi
  sample_case="$2"
fi

ps_lines="$(collect_ps_lines "$sample_case")"

typeset -i canonical_count=0
typeset -i noncanonical_count=0
typeset -a canonical_pids=()
typeset -a noncanonical_rows=()

echo "CANONICAL_CODEX=${CANONICAL_CODEX}"
echo "PID      | TYPE          | COMMAND"
echo "---------+---------------+--------------------------------------------------------------"

if [[ -n "$ps_lines" ]]; then
  while IFS= read -r raw_line; do
    [[ -z "$raw_line" ]] && continue

    local_line="${raw_line#*:}"
    pid="$(awk '{print $2}' <<< "$local_line")"
    cmd="$(awk '{for (i=11; i<=NF; i++) printf "%s%s", $i, (i<NF ? OFS : "")}' OFS=' ' <<< "$local_line")"
    if [[ -z "$cmd" ]]; then
      cmd="$local_line"
    fi

    if [[ "$cmd" == "${CANONICAL_CODEX} app-server"* ]]; then
      type="canonical"
      canonical_count+=1
      canonical_pids+=("$pid")
    else
      type="non-canonical"
      noncanonical_count+=1
      noncanonical_rows+=("$pid|$cmd")
    fi

    printf "%-8s | %-13s | %s\n" "$pid" "$type" "$cmd"
  done <<< "$ps_lines"
fi

echo
if (( canonical_count > 1 )); then
  echo "ERROR: multiple canonical codex app-servers"
  echo "Canonical PIDs: ${canonical_pids[*]}"
  exit 2
fi

if (( noncanonical_count > 0 )); then
  echo "Detected non-canonical codex app-server:"
  for row in "${noncanonical_rows[@]}"; do
    pid="${row%%|*}"
    cmd="${row#*|}"
    path="${cmd%% *}"
    echo "PID=${pid} PATH=${path}"
  done
  echo "Recommended controlled shutdown:"
  for row in "${noncanonical_rows[@]}"; do
    pid="${row%%|*}"
    echo "kill -TERM ${pid}"
  done
  exit 3
fi

if (( canonical_count == 1 )); then
  echo "OK: single canonical codex app-server"
  exit 0
fi

echo "ERROR: canonical codex app-server not found"
echo "Start Codex.app, then rerun tools/ops/check_codex_overlap.zsh"
exit 2
