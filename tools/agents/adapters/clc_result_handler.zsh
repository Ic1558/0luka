#!/bin/zsh

setopt err_return no_unset pipe_fail

wo_basename="${WO_FILE:t}"

if [[ "$wo_basename" == "RESULT-WO-DIRECT-PIPE-PROOF-001.md" ]]; then
  if [[ -r "$WO_FILE" ]] && [[ -s "$WO_FILE" ]]; then
    FOLLOWUP_WO="${AI_INBOX_ROOT}/codex/inbox/WO-CLC-FOLLOWUP-DIRECT-PIPE-001.md"
    write_artifact "$FOLLOWUP_WO" "$(printf '# WO-CLC-FOLLOWUP-DIRECT-PIPE-001\nsource_result: %s\nissued_by: clc\nissued_at: %s\n\nCLC received Codex result and is issuing autonomous follow-up.\n\n## DEFINITION OF DONE\n- [ ] Codex confirms receipt and returns RESULT confirming chain is closed\n' "${WO_FILE}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)")"
    ADAPTER_ARTIFACT_PATH="$FOLLOWUP_WO"
  else
    ADAPTER_ARTIFACT_PATH="${AI_INBOX_ROOT}/clc/inbox/BLOCKED-CLC-FOLLOWUP-DIRECT-PIPE-001.md"
    write_artifact "$ADAPTER_ARTIFACT_PATH" "BLOCKED-CLC-FOLLOWUP: could not produce follow-up from ${WO_FILE} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  fi
else
  ADAPTER_ARTIFACT_PATH="${AI_INBOX_ROOT}/clc/outbox/ACK-RESULT-${WO_ID}.md"
  write_artifact "$ADAPTER_ARTIFACT_PATH" "ACK: clc received ${WO_ID} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
fi
