#!/bin/zsh
# 0luka Knowledge Collator v2.0
# Purpose: Collate 0luka intelligence for NotebookLM ingestion with deterministic path governance.

emulate -L zsh
set -euo pipefail
setopt null_glob

SCRIPT_DIR="${0:A:h}"
REPO_ROOT="${SCRIPT_DIR:h}"

CANONICAL_GOV_ROOT="${REPO_ROOT}/core_brain/governance"
FALLBACK_GOV_ROOT="${REPO_ROOT}/core/governance"
MANUALS_ROOT="${REPO_ROOT}/g/manuals"
PLANS_ROOT="${REPO_ROOT}/interface/plans"
BEACON_PATH="${REPO_ROOT}/observability/stl/ledger/global_beacon.jsonl"
OUTPUT_DIR="${NOTEBOOK_INGEST_DIR:-${REPO_ROOT}/observability/notebook_ingest}"

PROMPT_CANDIDATES=(
  "${REPO_ROOT}/MASTER_PROMPT.md"
  "${REPO_ROOT}/cole/PROMPT.md"
  "${REPO_ROOT}/modules/ops/PHASE_COLE_RUN_CODEX_PROMPT.md"
)

MODE="run"
if [[ "${1:-}" == "--check" ]]; then
  MODE="check"
fi

resolve_governance_root() {
  if [[ -d "${CANONICAL_GOV_ROOT}" ]]; then
    print -- "${CANONICAL_GOV_ROOT}"
    return 0
  fi
  if [[ "${ALLOW_GOV_FALLBACK:-0}" == "1" && -d "${FALLBACK_GOV_ROOT}" ]]; then
    print -- "WARNING: using fallback governance root: ${FALLBACK_GOV_ROOT}" >&2
    print -- "${FALLBACK_GOV_ROOT}"
    return 0
  fi
  print -- "ERROR: missing canonical governance root: ${CANONICAL_GOV_ROOT}" >&2
  print -- "ACTION: restore core_brain/governance or set ALLOW_GOV_FALLBACK=1 for temporary fallback." >&2
  return 2
}

select_master_prompt() {
  local candidate
  for candidate in "${PROMPT_CANDIDATES[@]}"; do
    if [[ -f "${candidate}" ]]; then
      print -- "${candidate}"
      return 0
    fi
  done
  return 1
}

run_check_mode() {
  local gov_root prompt_src
  gov_root="$(resolve_governance_root)"
  print -- "CHECK repo_root=${REPO_ROOT}"
  print -- "CHECK output_dir=${OUTPUT_DIR}"
  print -- "CHECK governance_root=${gov_root}"
  if [[ -d "${PLANS_ROOT}" ]]; then
    print -- "CHECK plans_root=${PLANS_ROOT}"
  else
    print -- "WARNING: plans root missing, skipping plans: ${PLANS_ROOT}"
  fi
  if prompt_src="$(select_master_prompt)"; then
    print -- "CHECK master_prompt_source=${prompt_src}"
  else
    print -- "WARNING: no master prompt source found from precedence list."
    return 1
  fi
  return 0
}

copy_governance_docs() {
  local gov_root="$1"
  local gov_md_files protocol_src
  gov_md_files=( "${gov_root}"/*.md(N) )

  if [[ ${#gov_md_files[@]} -gt 0 ]]; then
    cp "${gov_md_files[@]}" "${OUTPUT_DIR}/"
  fi

  protocol_src="${gov_root}/agent_culture.md"
  if [[ -f "${protocol_src}" ]]; then
    cp "${protocol_src}" "${OUTPUT_DIR}/CORE_PROTOCOL.md"
  else
    print -- "WARNING: missing protocol source: ${protocol_src}"
  fi
}

copy_manuals() {
  local manual_files
  if [[ ! -d "${MANUALS_ROOT}" ]]; then
    return 0
  fi
  manual_files=( "${MANUALS_ROOT}"/*.md(N) )
  if [[ ${#manual_files[@]} -gt 0 ]]; then
    cp "${manual_files[@]}" "${OUTPUT_DIR}/"
  fi
}

copy_recent_beacon() {
  if [[ -f "${BEACON_PATH}" ]]; then
    tail -n 100 "${BEACON_PATH}" > "${OUTPUT_DIR}/RECENT_BEACON.json"
  fi
}

copy_recent_plans() {
  local plan_files=()
  if [[ ! -d "${PLANS_ROOT}" ]]; then
    print -- "WARNING: plans root missing, skipping plans: ${PLANS_ROOT}"
    return 0
  fi

  plan_files=( "${PLANS_ROOT}"/*.json(Nom[1,5]) )
  if [[ ${#plan_files[@]} -gt 0 ]]; then
    cp "${plan_files[@]}" "${OUTPUT_DIR}/"
  fi
}

copy_master_prompt() {
  local prompt_src="$1"
  cp "${prompt_src}" "${OUTPUT_DIR}/MASTER_PROMPT.md"
  print -- "INFO: master_prompt_source=${prompt_src}"
}

main() {
  local gov_root prompt_src
  if [[ "${MODE}" == "check" ]]; then
    run_check_mode
    return $?
  fi
  gov_root="$(resolve_governance_root)"

  mkdir -p "${OUTPUT_DIR}"
  print -- "INFO: collating notebook ingest into ${OUTPUT_DIR}"
  print -- "INFO: governance_root=${gov_root}"

  copy_governance_docs "${gov_root}"
  copy_manuals
  copy_recent_beacon
  copy_recent_plans

  if prompt_src="$(select_master_prompt)"; then
    copy_master_prompt "${prompt_src}"
  else
    print -- "WARNING: no master prompt source found from precedence list."
  fi

  print -- "INFO: done"
}

main "$@"
