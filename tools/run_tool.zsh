#!/bin/zsh
# tools/run_tool.zsh
# Wrapper for 0luka Tool Dispatching (Restored Phase 3.5)

TOOL_VERB=$1
shift

# Default Identity if not set
: ${AGENT_ID:=user}

case $TOOL_VERB in
    save)
        MSG="${1:-State Saved by $AGENT_ID}"
        echo "[0luka] Saving state (Agent: $AGENT_ID)..."
        git add .
        git commit -m "$MSG"
        ;;
    discover)
        echo "[0luka] Discovering workspace..."
        ls -F
        ;;
    verify-core)
        echo "[0luka] Verifying Core Integrity..."
        EXIT_CODE=0
        CORE_FILES=("core_brain/governance/agents.md" "core_brain/governance/router.md" "0luka.md")
        for f in "${CORE_FILES[@]}"; do
            if [[ -f "$f" ]]; then
                echo "  ✅ $f: EXISTS"
            else
                echo "  ❌ $f: MISSING"
                EXIT_CODE=1
            fi
        done
        return $EXIT_CODE
        ;;
    verify-health)
        echo "[0luka] Running Pre-Claim Health Gate..."
        zsh tools/ops/pre_claim_gate.zsh
        ;;
    apply-patch)
        PLAN=$1
        echo "[0luka] Applying Patch Plan: $PLAN..."
        python3 tools/patch/apply_patch.py "$PLAN"
        ;;
    warroom)
        echo "[0luka] Opening Decision Box (Warroom)..."
        zsh tools/ops/decision_box.zsh "$@"
        ;;
    lock-refresh)
        echo "[0luka] Refreshing Governance Lock Manifest..."
        python3 tools/ops/governance_file_lock.py --build-manifest "$@"
        ;;
    lock-verify)
        echo "[0luka] Verifying Governance Integrity..."
        python3 tools/ops/governance_file_lock.py --verify-manifest "$@"
        ;;
    cole-run)
        SUBCMD="${1:-}"
        if [[ -z "$SUBCMD" ]]; then
            echo "Error: missing cole-run subcommand"
            echo "Usage: run_tool.zsh cole-run {list|latest|show <run_id>}"
            exit 2
        fi
        shift
        zsh cole/tools/cole_run.zsh "$SUBCMD" "$@"
        ;;
    *)
        echo "Error: Unknown tool verb '$TOOL_VERB'"
        echo "Available: save, discover, verify-core, verify-health, apply-patch, cole-run, warroom, lock-refresh, lock-verify"
        exit 1
        ;;
esac
