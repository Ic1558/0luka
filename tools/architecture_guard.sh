#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DOCS_DIR="$ROOT_DIR/docs/architecture"

append_issue() {
  current_value=$1
  issue=$2
  if [ -z "$current_value" ]; then
    printf '%s' "$issue"
  else
    printf '%s\n%s' "$current_value" "$issue"
  fi
}

print_status_section() {
  label=$1
  status=$2
  issues=$3

  printf '%s: %s\n' "$label" "$status"
  if [ -n "$issues" ]; then
    printf '%s\n' "$issues" | while IFS= read -r line; do
      [ -n "$line" ] && printf '  - %s\n' "$line"
    done
  fi
}

check_file() {
  [ -f "$ROOT_DIR/$1" ]
}

resolve_repo_path() {
  rel=$1
  rel=${rel#./}
  printf '%s/%s' "$ROOT_DIR" "$rel"
}

canonical_docs_status=PASS
canonical_docs_issues=''

capability_docs_status=PASS
capability_docs_issues=''

runtime_ownership_status=PASS
runtime_ownership_issues=''

layer_mapping_status=PASS
layer_mapping_issues=''

runtime_entrypoints_status=PASS
runtime_entrypoints_issues=''

runtime_first_hop_status=PASS
runtime_first_hop_issues=''

architecture_invariants_status=PASS
architecture_invariants_issues=''

unresolved_rules=''

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
    canonical_docs_issues=$(append_issue "$canonical_docs_issues" "missing $rel")
  fi
done

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
    capability_docs_issues=$(append_issue "$capability_docs_issues" "missing $rel")
  fi
done

if grep -nE 'Antigravity-HQ.+canonical runtime' \
  "$DOCS_DIR/mac-mini-runtime-inventory.md" >/dev/null 2>&1; then
  runtime_ownership_status=FAIL
  runtime_ownership_issues=$(append_issue "$runtime_ownership_issues" 'Antigravity-HQ canonical ownership conflict detected')
fi

if grep -nF '/Users/icmini/0luka/repos/option/modules/antigravity/realtime/control_tower.py' \
  "$DOCS_DIR/controltower-runtime-version-endpoint.md" >/dev/null 2>&1; then
  runtime_ownership_status=FAIL
  runtime_ownership_issues=$(append_issue "$runtime_ownership_issues" 'legacy app-local path treated as maintained source in controltower runtime doc')
fi

if grep -nE 'repos/option.+canonical runtime' \
  "$DOCS_DIR"/*.md "$DOCS_DIR"/capabilities/*.md >/dev/null 2>&1; then
  runtime_ownership_status=FAIL
  runtime_ownership_issues=$(append_issue "$runtime_ownership_issues" 'repos/option treated as canonical runtime ownership in architecture docs')
fi

if ! grep -nF 'runtime/services/antigravity_scan/runner.zsh' \
  "$DOCS_DIR/0LUKA_ARCHITECTURE_DIAGRAM.md" >/dev/null 2>&1; then
  runtime_ownership_status=FAIL
  runtime_ownership_issues=$(append_issue "$runtime_ownership_issues" 'canonical Antigravity scan wrapper reference missing from architecture diagram')
fi

if ! grep -nF 'runtime/services/antigravity_realtime/runner.zsh' \
  "$DOCS_DIR/0LUKA_ARCHITECTURE_DIAGRAM.md" >/dev/null 2>&1; then
  runtime_ownership_status=FAIL
  runtime_ownership_issues=$(append_issue "$runtime_ownership_issues" 'canonical Antigravity realtime wrapper reference missing from architecture diagram')
fi

if ! grep -nF 'PM2 must not directly target app scripts' \
  "$DOCS_DIR/0LUKA_ARCHITECTURE_CONTRACT.md" >/dev/null 2>&1; then
  architecture_invariants_status=FAIL
  architecture_invariants_issues=$(append_issue "$architecture_invariants_issues" 'architecture contract is missing the non-canonical PM2 first-hop rule')
fi

layer_model_has_modules=$(grep -nF 'Modules may depend on:' "$DOCS_DIR/0LUKA_LAYER_MODEL.md" >/dev/null 2>&1 && printf yes || printf no)
layer_model_has_core=$(grep -nF 'Core must not depend on:' "$DOCS_DIR/0LUKA_LAYER_MODEL.md" >/dev/null 2>&1 && printf yes || printf no)
guardrails_has_runtime_forbidden=$(grep -nF 'Runtime -> Interface' "$DOCS_DIR/0LUKA_ARCHITECTURE_GUARDRAILS.md" >/dev/null 2>&1 && printf yes || printf no)

if [ "$layer_model_has_modules" = yes ] && [ "$layer_model_has_core" = yes ] && [ "$guardrails_has_runtime_forbidden" = yes ] && \
   grep -nF 'agents/' "$DOCS_DIR/0LUKA_LAYER_MODEL.md" >/dev/null 2>&1 && \
   ! grep -nF 'System / Services Layer' "$DOCS_DIR/0LUKA_ARCHITECTURE_GUARDRAILS.md" >/dev/null 2>&1; then
  if find "$ROOT_DIR/core" -type f \( -name '*.py' -o -name '*.js' \) 2>/dev/null | xargs grep -nE '(^|[[:space:]])(from|import)[[:space:]]+(runtime|modules|interface)(\.|[[:space:]]|$)|from[[:space:]]+["'\''](runtime|modules|interface)/|require\(["'\''](runtime|modules|interface)/' >/dev/null 2>&1; then
    layer_mapping_status=FAIL
    layer_mapping_issues=$(append_issue "$layer_mapping_issues" 'core imports higher-layer paths (runtime/modules/interface)')
  fi

  if find "$ROOT_DIR/runtime" -type f \( -name '*.py' -o -name '*.js' \) 2>/dev/null | xargs grep -nE '(^|[[:space:]])(from|import)[[:space:]]+(interface|modules)(\.|[[:space:]]|$)|from[[:space:]]+["'\''](interface|modules)/|require\(["'\''](interface|modules)/' >/dev/null 2>&1; then
    layer_mapping_status=FAIL
    layer_mapping_issues=$(append_issue "$layer_mapping_issues" 'runtime imports higher or sideways layer paths (interface/modules)')
  fi

  if find "$ROOT_DIR/modules" -type f \( -name '*.py' -o -name '*.js' \) 2>/dev/null | xargs grep -nE '(^|[[:space:]])(from|import)[[:space:]]+interface(\.|[[:space:]]|$)|from[[:space:]]+["'\'']interface/|require\(["'\'']interface/' >/dev/null 2>&1; then
    layer_mapping_status=FAIL
    layer_mapping_issues=$(append_issue "$layer_mapping_issues" 'modules import interface paths')
  fi
else
  layer_mapping_status=UNRESOLVED
  layer_mapping_issues=$(append_issue "$layer_mapping_issues" 'canonical docs do not yet define a stable enough path-to-layer mapping for static import enforcement')
fi

if ! grep -nF 'agents/' "$DOCS_DIR/0LUKA_LAYER_MODEL.md" >/dev/null 2>&1; then
  unresolved_rules=$(append_issue "$unresolved_rules" 'Agents layer mapping')
  if [ "$layer_mapping_status" = PASS ]; then
    layer_mapping_status=UNRESOLVED
  fi
fi

if grep -nF 'System / Services Layer' "$DOCS_DIR/0LUKA_ARCHITECTURE_GUARDRAILS.md" >/dev/null 2>&1; then
  unresolved_rules=$(append_issue "$unresolved_rules" 'System / Services vs layer-model terminology alignment')
  if [ "$layer_mapping_status" = PASS ]; then
    layer_mapping_status=UNRESOLVED
  fi
fi

runtime_ref_paths=$( \
  {
    grep -RhoE 'repos/option/src/[A-Za-z0-9_./-]+\.(py|js)' "$ROOT_DIR/runtime/services" 2>/dev/null || true
    grep -RhoE 'repos/option/src/[A-Za-z0-9_./-]+\.(py|js)' "$ROOT_DIR/runtime/supervisors" 2>/dev/null || true
    sed -n 's/.*delegates to `\(repos\/option\/src\/[A-Za-z0-9_./-]\+\)`/\1/p' \
      "$ROOT_DIR/runtime/supervisors/ANTIGRAVITY_RUNTIME_OWNERSHIP.md" 2>/dev/null || true
    sed -n 's/.*delegated implementation: `\(repos\/option\/src\/[A-Za-z0-9_./-]\+\)`/\1/p' \
      "$ROOT_DIR/runtime/services/antigravity_scan/README.md" \
      "$ROOT_DIR/runtime/services/antigravity_realtime/README.md" 2>/dev/null || true
  } | grep -v '__pycache__' | sort -u \
)

if [ -n "$runtime_ref_paths" ]; then
  printf '%s\n' "$runtime_ref_paths" | while IFS= read -r rel_path; do
    [ -n "$rel_path" ] || continue
    abs_path=$(resolve_repo_path "$rel_path")
    if [ ! -e "$abs_path" ]; then
      printf '%s\n' "$rel_path"
    fi
  done >/tmp/architecture_guard_missing_paths.txt
else
  : >/tmp/architecture_guard_missing_paths.txt
fi

if [ -s /tmp/architecture_guard_missing_paths.txt ]; then
  runtime_entrypoints_status=FAIL
  while IFS= read -r rel_path; do
    [ -n "$rel_path" ] || continue
    runtime_entrypoints_issues=$(append_issue "$runtime_entrypoints_issues" "canonical wrapper-owned delegated path missing: $rel_path")
  done </tmp/architecture_guard_missing_paths.txt
fi

pm2_start_file="$ROOT_DIR/runtime/services/antigravity_bootstrap/pm2_start.zsh"
if [ -f "$pm2_start_file" ]; then
  if grep -nE 'pm2 start .*"(repos|src|modules)/|pm2 start .* (repos|src|modules)/' "$pm2_start_file" >/dev/null 2>&1; then
    runtime_first_hop_status=FAIL
    runtime_first_hop_issues=$(append_issue "$runtime_first_hop_issues" 'pm2_start.zsh starts app-local scripts directly instead of runtime-owned wrappers')
  fi

  wrapper_targets=$(sed -n 's/^[A-Z_][A-Z0-9_]*="\$ROOT_DIR\/\(runtime\/services\/[^"]*\)"$/\1/p' "$pm2_start_file")
  if [ -z "$wrapper_targets" ]; then
    runtime_first_hop_status=FAIL
    runtime_first_hop_issues=$(append_issue "$runtime_first_hop_issues" 'pm2_start.zsh does not declare runtime/services first-hop wrapper targets')
  fi
fi

if [ -d "$ROOT_DIR/runtime/services" ]; then
  if grep -RhoE 'exec[[:space:]].*(modules|src|repos)/[A-Za-z0-9_./-]+' "$ROOT_DIR/runtime/services" 2>/dev/null | grep -v 'delegated implementation' >/dev/null 2>&1; then
    :
  fi
fi

for unresolved_title in \
  'Host Supervisor Authority Model' \
  'Antigravity HQ Runtime Ownership'
do
  unresolved_rules=$(append_issue "$unresolved_rules" "$unresolved_title")
done

if grep -Rho 'ADR-UNRESOLVED: [^`]*' "$DOCS_DIR/0LUKA_ARCHITECTURE_CONTRACT.md" "$DOCS_DIR/0LUKA_ARCHITECTURE_INVARIANTS.md" 2>/dev/null | sed 's/ADR-UNRESOLVED: //' | sort -u >/tmp/architecture_guard_unresolved.txt; then
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    case "$unresolved_rules" in
      *"$line"*)
        ;;
      *)
        unresolved_rules=$(append_issue "$unresolved_rules" "$line")
        ;;
    esac
  done </tmp/architecture_guard_unresolved.txt
fi

overall=PASS
exit_code=0

if [ "$canonical_docs_status" = FAIL ] || \
   [ "$capability_docs_status" = FAIL ] || \
   [ "$runtime_ownership_status" = FAIL ] || \
   [ "$layer_mapping_status" = FAIL ] || \
   [ "$runtime_entrypoints_status" = FAIL ] || \
   [ "$runtime_first_hop_status" = FAIL ] || \
   [ "$architecture_invariants_status" = FAIL ]; then
  overall=FAIL
  exit_code=1
fi

printf '%s\n' '0LUKA Architecture Guard'
printf '\n'
print_status_section 'Canonical docs' "$canonical_docs_status" "$canonical_docs_issues"
print_status_section 'Capability docs' "$capability_docs_status" "$capability_docs_issues"
print_status_section 'Runtime ownership' "$runtime_ownership_status" "$runtime_ownership_issues"
print_status_section 'Layer mapping' "$layer_mapping_status" "$layer_mapping_issues"
print_status_section 'Runtime entrypoints' "$runtime_entrypoints_status" "$runtime_entrypoints_issues"
print_status_section 'Runtime first-hop ownership' "$runtime_first_hop_status" "$runtime_first_hop_issues"
print_status_section 'Architecture invariants' "$architecture_invariants_status" "$architecture_invariants_issues"
printf 'Unresolved rules:\n'
if [ -n "$unresolved_rules" ]; then
  printf '%s\n' "$unresolved_rules" | while IFS= read -r line; do
    [ -n "$line" ] && printf '  - %s\n' "$line"
  done
else
  printf '  - none\n'
fi
printf 'Overall result: %s\n' "$overall"
exit "$exit_code"
