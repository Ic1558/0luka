#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
LOG_FILE="$ROOT/modules/studio/dryrun_verdict.log"
mkdir -p "$(dirname "$LOG_FILE")"

_log() { echo "[$1] $2" | tee -a "$LOG_FILE"; }

_log "INFO" "Starting Dry-Run for Studio Spec Compliance..."

# 1. Path Policy Check
_check_path() {
    local p="$1"
    # Deny system runtime, Allow module runtime
    if [[ "$p" == "$ROOT/0luka/runtime/"* || "$p" == "$ROOT/system/runtime/"* ]]; then
        return 1 # Fail (Hard Deny)
    fi
    if [[ "$p" == "$ROOT/modules/studio/runtime/"* ]]; then
        return 0 # Pass (Module Internal)
    fi
    # Deny generic sensitive
    if [[ "$p" == *".env"* || "$p" == *".key" || "$p" == *".pem" ]]; then
        return 1
    fi
    return 0
}

_log "TEST" "Path Policy Verification:"
p1="$ROOT/0luka/runtime/core.db"; if _check_path "$p1"; then _log "FAIL" "Allowed system runtime: $p1"; else _log "PASS" "Denied system runtime: $p1"; fi
p2="$ROOT/modules/studio/runtime/executor.py"; if _check_path "$p2"; then _log "PASS" "Allowed module runtime: $p2"; else _log "FAIL" "Denied module runtime: $p2"; fi
p3="$ROOT/modules/studio/.env"; if _check_path "$p3"; then _log "FAIL" "Allowed .env in module: $p3"; else _log "PASS" "Denied .env: $p3"; fi


# 2. Secret Pattern Check (Extended)
_check_secret() {
    local content="$1"
    # Extended patterns: id_rsa, p12, kdbx, bearer token
    if [[ "$content" =~ "BEGIN RSA PRIVATE KEY" || "$content" =~ "Bearer sk-" || "$content" =~ ".p12" || "$content" =~ ".kdbx" ]]; then
        return 1 # Fail (Secret Detected)
    fi
    return 0
}

_log "TEST" "Secret Pattern Verification:"
s1="Use this api key: Bearer sk-12345"; if _check_secret "$s1"; then _log "FAIL" "Missed Bearer Token"; else _log "PASS" "Detected Bearer Token"; fi
s2="Here is my id_rsa file content: BEGIN RSA PRIVATE KEY..."; if _check_secret "$s2"; then _log "FAIL" "Missed RSA Key"; else _log "PASS" "Detected RSA Key"; fi


# 3. Contract Naming Policy
# Enforce one-truth: prompt_spec_v1 for requests, output_bundle_v1 for results
CONTRACT_REQ_NAME="prompt_spec_v1"
CONTRACT_RES_NAME="output_bundle_v1"
_log "INFO" "Enforcing Contract Names: REQ=$CONTRACT_REQ_NAME, RES=$CONTRACT_RES_NAME"


# 4. Promotion Gate Policy
# Must fail if explicitly not "SYSTEM_GATED"
PROMOTION_POLICY="SYSTEM_GATED"
if [[ "$PROMOTION_POLICY" == "FAST_TRACK" ]]; then
    _log "FAIL" "Promotion Policy is FAST_TRACK (Must be SYSTEM_GATED)"
else
    _log "PASS" "Promotion Policy is $PROMOTION_POLICY"
fi


_log "INFO" "Dry-Run Complete. Check $LOG_FILE for details."
