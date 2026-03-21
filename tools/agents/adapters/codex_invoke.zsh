#!/bin/zsh

setopt err_return no_unset pipe_fail

RESULT_FILE="${AI_INBOX_ROOT}/clc/inbox/RESULT-${WO_ID}.md"
LOG_FILE="${LOG_DIR}/codex_exec_${WO_ID}.log"

codex exec --ephemeral -o "$RESULT_FILE" "$(cat "$WO_FILE")" 2>>"$LOG_FILE"
EXIT_CODE=$?

if [[ $EXIT_CODE -ne 0 ]]; then
  ADAPTER_ARTIFACT_PATH="${AI_INBOX_ROOT}/clc/inbox/FAILED-CODEX-${WO_ID}.md"
  write_artifact "$ADAPTER_ARTIFACT_PATH" "FAILED: codex exec exited ${EXIT_CODE} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  return $EXIT_CODE
fi

ADAPTER_ARTIFACT_PATH="$RESULT_FILE"
