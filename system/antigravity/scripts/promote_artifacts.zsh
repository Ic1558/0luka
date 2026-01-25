#!/usr/bin/env zsh
set -euo pipefail

BRAIN_DIR="/Users/icmini/.gemini/antigravity/brain/e488f23e-d776-4a9f-9782-3e1d4842fc57"
TARGET_ROOT="${HOME}/0luka/observability/antigravity_tmp"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

setopt nullglob

# Ensure target dirs (redundant if retention script ran, but safe)
mkdir -p "${TARGET_ROOT}/tasks" "${TARGET_ROOT}/implementation_plan" "${TARGET_ROOT}/phase_reports" "${TARGET_ROOT}/walkthrough"

# 1. Promote Task Log
if [[ -f "${BRAIN_DIR}/task.md" ]]; then
    cp "${BRAIN_DIR}/task.md" "${TARGET_ROOT}/tasks/task_${TIMESTAMP}.md"
    print "Promoted: task.md -> tasks/task_${TIMESTAMP}.md"
fi

# 2. Promote Implementation Plan
if [[ -f "${BRAIN_DIR}/implementation_plan.md" ]]; then
    cp "${BRAIN_DIR}/implementation_plan.md" "${TARGET_ROOT}/implementation_plan/plan_${TIMESTAMP}.md"
    print "Promoted: implementation_plan.md -> implementation_plan/plan_${TIMESTAMP}.md"
fi

# 3. Promote Walkthrough
if [[ -f "${BRAIN_DIR}/walkthrough.md" ]]; then
    cp "${BRAIN_DIR}/walkthrough.md" "${TARGET_ROOT}/walkthrough/walkthrough_${TIMESTAMP}.md"
    print "Promoted: walkthrough.md -> walkthrough/walkthrough_${TIMESTAMP}.md"
fi

# 4. Promote OnePagers / GRs
for f in "${BRAIN_DIR}"/Handover_OnePager*.md "${BRAIN_DIR}"/GR_*.md; do
    if [[ -f "$f" ]]; then
        base=$(basename "$f")
        cp "$f" "${TARGET_ROOT}/phase_reports/${base%.md}_${TIMESTAMP}.md"
        print "Promoted: $base -> phase_reports/${base%.md}_${TIMESTAMP}.md"
    fi
done

print "Done. Artifacts secured in 0luka Store."
