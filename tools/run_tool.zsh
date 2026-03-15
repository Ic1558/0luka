#!/bin/zsh
# tools/run_tool.zsh
# Wrapper for 0luka Tool Dispatching (Restored Phase 3.5)

TOOL_VERB=$1
shift

# Default Identity if not set
: ${AGENT_ID:=user}

case $TOOL_VERB in
    save)
        # BLOCKED — ADR-GIT-001: automated 'git add .' is forbidden against the
        # live canonical repo. Mass-staging via automation was a contributing
        # factor in the 2026-03-15 Git object store corruption incident.
        #
        # Use save-now v2 protocol instead:
        #   ~/0luka/tools/save_now.zsh --phase done --agent-id <id> --trace-id <id> --in <file>
        #
        # For explicit human-reviewed commits, use git directly from a terminal session.
        echo "[0luka] ERROR: 'run_tool save' is permanently blocked." >&2
        echo "  Reason: automated 'git add .' risks corrupting the live Git object store." >&2
        echo "  Use: ~/0luka/tools/save_now.zsh (artifact-only, no git writes)" >&2
        echo "  See: docs/architecture/adr/ADR-GIT-001-git-safety-rules.md" >&2
        exit 1
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
        echo "Available: save, discover, verify-core, verify-health, apply-patch, cole-run"
        exit 1
        ;;
esac
