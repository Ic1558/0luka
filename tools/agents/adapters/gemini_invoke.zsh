#!/bin/zsh

setopt err_return no_unset pipe_fail

RESULT_FILE="${AI_INBOX_ROOT}/clc/inbox/RESULT-GEMINI-${WO_ID}.md"
LOG_FILE="${LOG_DIR}/gemini_exec_${WO_ID}.log"

gemini -p "$(cat "$WO_FILE")" > "${RESULT_FILE}.tmp" 2>>"$LOG_FILE"
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  ADAPTER_ARTIFACT_PATH="${AI_INBOX_ROOT}/clc/inbox/FAILED-GEMINI-${WO_ID}.md"
  write_artifact "$ADAPTER_ARTIFACT_PATH" "FAILED: gemini exited ${EXIT_CODE} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  return $EXIT_CODE
fi

/bin/mv "${RESULT_FILE}.tmp" "$RESULT_FILE"
ADAPTER_ARTIFACT_PATH="$RESULT_FILE"
