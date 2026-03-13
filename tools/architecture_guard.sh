#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

PASS=true

print_section() {
  printf '%s\n' "$1"
}

fail_item() {
  PASS=false
  printf '  - %s\n' "$1"
}

check_file() {
  [ -f "$ROOT_DIR/$1" ]
}

canonical_docs_status=PASS
capability_docs_status=PASS
runtime_ownership_status=PASS
architecture_invariants_status=PASS

missing_canonical=""
for rel in \
  docs/architecture/0LUKA_ARCHITECTURE_CONTRACT.md \
  docs/architecture/0LUKA_ARCHITECTURE_INVARIANTS.md \
  docs/architecture/0LUKA_LAYER_MODEL.md \
  docs/architecture/0LUKA_ARCHITECTURE_GUARDRAILS.md \
  docs/architecture/0LUKA_CAPABILITY_MAP.md \
  docs/architecture/0LUKA_ARCHITECTURE_DIAGRAM.md
do
  if ! check_file "$rel"; then
    canonical_docs_status=FAIL
    missing_canonical="${missing_canonical}${rel}
"
  fi
done

missing_caps=""
for rel in \
  docs/architecture/capabilities/operator_control.md \
  docs/architecture/capabilities/policy_governance.md \
  docs/architecture/capabilities/decision_infrastructure.md \
  docs/architecture/capabilities/runtime_execution.md \
  docs/architecture/capabilities/observability_intelligence.md \
  docs/architecture/capabilities/agent_execution.md \
  docs/architecture/capabilities/antigravity_module.md
do
  if ! check_file "$rel"; then
    capability_docs_status=FAIL
    missing_caps="${missing_caps}${rel}
"
  fi
done

DOCS_DIR="$ROOT_DIR/docs/architecture"

if grep -nE 'Antigravity-HQ.+canonical runtime' \
  "$DOCS_DIR/mac-mini-runtime-inventory.md" >/dev/null 2>&1; then
  runtime_ownership_status=FAIL
  runtime_hq_conflict=true
else
  runtime_hq_conflict=false
fi

if grep -nF '/Users/icmini/0luka/repos/option/modules/antigravity/realtime/control_tower.py' \
  "$DOCS_DIR/controltower-runtime-version-endpoint.md" >/dev/null 2>&1; then
  runtime_ownership_status=FAIL
  stale_controltower_claim=true
else
  stale_controltower_claim=false
fi

if grep -nE 'repos/option.+canonical runtime' \
  "$DOCS_DIR"/*.md "$DOCS_DIR"/capabilities/*.md >/dev/null 2>&1; then
  runtime_ownership_status=FAIL
  repos_option_claim=true
else
  repos_option_claim=false
fi

if ! grep -nF 'runtime/services/antigravity_scan/runner.zsh' \
  "$DOCS_DIR/0LUKA_ARCHITECTURE_DIAGRAM.md" >/dev/null 2>&1; then
  runtime_ownership_status=FAIL
  missing_scan_wrapper_ref=true
else
  missing_scan_wrapper_ref=false
fi

if ! grep -nF 'runtime/services/antigravity_realtime/runner.zsh' \
  "$DOCS_DIR/0LUKA_ARCHITECTURE_DIAGRAM.md" >/dev/null 2>&1; then
  runtime_ownership_status=FAIL
  missing_realtime_wrapper_ref=true
else
  missing_realtime_wrapper_ref=false
fi

if ! grep -nF 'PM2 must not directly target app scripts' \
  "$ROOT_DIR/docs/architecture/0LUKA_ARCHITECTURE_CONTRACT.md" >/dev/null 2>&1; then
  architecture_invariants_status=FAIL
  missing_contract_rule=true
else
  missing_contract_rule=false
fi

print_section '0LUKA Architecture Guard'
printf '\n'

printf 'Canonical docs: %s\n' "$canonical_docs_status"
if [ "$canonical_docs_status" = "FAIL" ]; then
  printf '%s' "$missing_canonical" | while IFS= read -r line; do
    [ -n "$line" ] && printf '  - missing %s\n' "$line"
  done
fi

printf 'Capability docs: %s\n' "$capability_docs_status"
if [ "$capability_docs_status" = "FAIL" ]; then
  printf '%s' "$missing_caps" | while IFS= read -r line; do
    [ -n "$line" ] && printf '  - missing %s\n' "$line"
  done
fi

printf 'Runtime ownership: %s\n' "$runtime_ownership_status"
if [ "$runtime_ownership_status" = "FAIL" ]; then
  [ "$runtime_hq_conflict" = true ] && \
    fail_item 'Antigravity-HQ canonical ownership conflict detected'
  [ "$stale_controltower_claim" = true ] && \
    fail_item 'legacy app-local path treated as maintained source in controltower runtime doc'
  [ "$repos_option_claim" = true ] && \
    fail_item 'repos/option treated as canonical runtime ownership in architecture docs'
  [ "$missing_scan_wrapper_ref" = true ] && \
    fail_item 'canonical Antigravity scan wrapper reference missing from architecture diagram'
  [ "$missing_realtime_wrapper_ref" = true ] && \
    fail_item 'canonical Antigravity realtime wrapper reference missing from architecture diagram'
fi

printf 'Architecture invariants: %s\n' "$architecture_invariants_status"
if [ "$architecture_invariants_status" = "FAIL" ]; then
  [ "$missing_contract_rule" = true ] && \
    fail_item 'architecture contract is missing the non-canonical PM2 first-hop rule'
fi

if [ "$PASS" = true ] && \
   [ "$canonical_docs_status" = "PASS" ] && \
   [ "$capability_docs_status" = "PASS" ] && \
   [ "$runtime_ownership_status" = "PASS" ] && \
   [ "$architecture_invariants_status" = "PASS" ]; then
  overall=PASS
  exit_code=0
else
  overall=FAIL
  exit_code=1
fi

printf 'Overall result: %s\n' "$overall"
exit "$exit_code"
