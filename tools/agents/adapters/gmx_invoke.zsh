#!/bin/zsh

setopt err_return no_unset pipe_fail

ADAPTER_ARTIFACT_PATH="${AI_INBOX_ROOT}/clc/inbox/HELD-GMX-${WO_ID}.md"
write_artifact "$ADAPTER_ARTIFACT_PATH" "HELD: gmx terminal handler received ${WO_ID} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
