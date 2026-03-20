#!/bin/zsh

setopt err_return no_unset pipe_fail

MISSION_ID="inbox-${WO_ID}"
OUTPUT_FILE="${LOG_DIR}/clc_${WO_ID}.json"

python3 "${WORKING_DIR}/tools/ops/run_mission.py" \
  --prompt "$(cat "$WO_FILE")" \
  --provider claude \
  --operator-id clc \
  --mission-id "$MISSION_ID" \
  > "$OUTPUT_FILE"
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  ADAPTER_ARTIFACT_PATH="${AI_INBOX_ROOT}/clc/inbox/FAILED-CLC-${WO_ID}.md"
  write_artifact "$ADAPTER_ARTIFACT_PATH" "FAILED: clc invoke exited ${EXIT_CODE} for ${WO_ID} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  return $EXIT_CODE
fi

if [[ "${WO_VERDICT}" == "PLAN-ONLY" ]]; then
  ADAPTER_ARTIFACT_PATH="${AI_INBOX_ROOT}/clc/outbox/PLAN-${WO_ID}.md"
else
  ADAPTER_ARTIFACT_PATH="${AI_INBOX_ROOT}/clc/inbox/RESULT-${WO_ID}.md"
fi

/bin/cp "$OUTPUT_FILE" "${ADAPTER_ARTIFACT_PATH}.tmp"
/bin/mv "${ADAPTER_ARTIFACT_PATH}.tmp" "$ADAPTER_ARTIFACT_PATH"
