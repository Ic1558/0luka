#!/usr/bin/env zsh
# ============================================================
# chatctl.zsh — Terminal CLI for 0luka Chat Control Plane
# ============================================================
# Usage: ./chatctl.zsh [command]
#        ./chatctl.zsh (interactive mode)
#
# Commands:
#   preview "your command"   - Preview a command
#   confirm <preview_id>     - Confirm and submit
#   watch <task_id>          - Watch task state
#   interactive              - Interactive chat mode
#
# SECURITY: This CLI only calls the web_bridge API.
#           NO direct execution.
# ============================================================

set -euo pipefail

# Configuration
API_BASE="${CHATCTL_API_BASE:-http://127.0.0.1:8000/api/v1/chat}"
SESSION_FILE="${HOME}/.0luka_chat_session"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================
# Session Management
# ============================================================

get_session_id() {
    if [[ -f "$SESSION_FILE" ]]; then
        cat "$SESSION_FILE"
    else
        local session_id=$(uuidgen | tr '[:upper:]' '[:lower:]')
        echo "$session_id" > "$SESSION_FILE"
        echo "$session_id"
    fi
}

# ============================================================
# API Calls
# ============================================================

call_preview() {
    local raw_input="$1"
    local session_id=$(get_session_id)

    curl -s -X POST "${API_BASE}/preview" \
        -H "Content-Type: application/json" \
        -d "{\"raw_input\": \"$raw_input\", \"channel\": \"terminal\", \"session_id\": \"$session_id\"}"
}

call_confirm() {
    local preview_id="$1"
    local session_id=$(get_session_id)

    curl -s -X POST "${API_BASE}/confirm" \
        -H "Content-Type: application/json" \
        -d "{\"preview_id\": \"$preview_id\", \"session_id\": \"$session_id\"}"
}

call_watch() {
    local task_id="$1"
    local session_id=$(get_session_id)

    curl -s -X GET "${API_BASE}/watch/${task_id}?session_id=${session_id}"
}

# ============================================================
# Display Functions
# ============================================================

show_preview() {
    local response="$1"

    # Parse JSON with jq if available
    if command -v jq &> /dev/null; then
        local preview_id=$(echo "$response" | jq -r '.preview_id // "unknown"')
        local intent=$(echo "$response" | jq -r '.normalized_task.intent // "unknown"')
        local risk=$(echo "$response" | jq -r '.risk // "unknown"')
        local lane=$(echo "$response" | jq -r '.lane // "unknown"')
        local tool=$(echo "$response" | jq -r '.normalized_task.operations[0].tool // "unknown"')
        local task_id=$(echo "$response" | jq -r '.normalized_task.task_id // "unknown"')
        local ttl=$(echo "$response" | jq -r '.ttl_seconds // 300')

        echo ""
        echo "${CYAN}═══════════════════════════════════════════════════════${NC}"
        echo "${BLUE}  PREVIEW${NC}"
        echo "${CYAN}═══════════════════════════════════════════════════════${NC}"
        echo ""
        echo "  ${YELLOW}Preview ID:${NC}  $preview_id"
        echo "  ${YELLOW}Task ID:${NC}     $task_id"
        echo "  ${YELLOW}Intent:${NC}      $intent"
        echo "  ${YELLOW}Tool:${NC}        $tool"

        if [[ "$risk" == "high" ]]; then
            echo "  ${YELLOW}Risk:${NC}        ${RED}$risk${NC}"
        else
            echo "  ${YELLOW}Risk:${NC}        ${GREEN}$risk${NC}"
        fi

        if [[ "$lane" == "approval" ]]; then
            echo "  ${YELLOW}Lane:${NC}        ${YELLOW}$lane (requires Boss approval)${NC}"
        else
            echo "  ${YELLOW}Lane:${NC}        ${GREEN}$lane (auto-execute)${NC}"
        fi

        echo "  ${YELLOW}Expires:${NC}     ${ttl}s"
        echo ""
        echo "${CYAN}═══════════════════════════════════════════════════════${NC}"
        echo ""

        # Return preview_id for confirm
        echo "$preview_id"
    else
        echo "${YELLOW}[Preview Response]${NC}"
        echo "$response"
    fi
}

show_confirm() {
    local response="$1"

    if command -v jq &> /dev/null; then
        local resp_status=$(echo "$response" | jq -r '.status // "error"')
        local task_id=$(echo "$response" | jq -r '.task_id // "unknown"')
        local resp_path=$(echo "$response" | jq -r '.path_written // "unknown"')
        local ack=$(echo "$response" | jq -r '.ack // ""')

        if [[ "$resp_status" == "ok" ]]; then
            echo ""
            echo "${GREEN}═══════════════════════════════════════════════════════${NC}"
            echo "${GREEN}  CONFIRMED${NC}"
            echo "${GREEN}═══════════════════════════════════════════════════════${NC}"
            echo ""
            echo "  ${GREEN}✓${NC} $ack"
            echo ""
            echo "  ${YELLOW}Task ID:${NC}  $task_id"
            echo "  ${YELLOW}Path:${NC}     $resp_path"
            echo ""
            echo "${GREEN}═══════════════════════════════════════════════════════${NC}"
            echo ""
            # Return task_id for watch
            echo "$task_id"
        else
            echo ""
            echo "${RED}═══════════════════════════════════════════════════════${NC}"
            echo "${RED}  ERROR${NC}"
            echo "${RED}═══════════════════════════════════════════════════════${NC}"
            echo ""
            echo "  ${RED}✗${NC} $(echo "$response" | jq -r '.detail // "Unknown error"')"
            echo ""
        fi
    else
        echo "${YELLOW}[Confirm Response]${NC}"
        echo "$response"
    fi
}

show_watch() {
    local response="$1"

    if command -v jq &> /dev/null; then
        local task_id=$(echo "$response" | jq -r '.task_id // "unknown"')
        local state=$(echo "$response" | jq -r '.state // "unknown"')
        local updated=$(echo "$response" | jq -r '.updated_at // ""')

        local state_color="$YELLOW"
        local state_icon="⏳"

        case "$state" in
            "done")
                state_color="$GREEN"
                state_icon="✓"
                ;;
            "failed")
                state_color="$RED"
                state_icon="✗"
                ;;
            "running")
                state_color="$CYAN"
                state_icon="▶"
                ;;
            "pending_approval")
                state_color="$YELLOW"
                state_icon="⏸"
                ;;
            "accepted")
                state_color="$BLUE"
                state_icon="◉"
                ;;
        esac

        echo "  [${state_color}${state_icon}${NC}] Task ${task_id}: ${state_color}${state}${NC}  (${updated})"
    else
        echo "$response"
    fi
}

# ============================================================
# Interactive Mode
# ============================================================

run_interactive() {
    echo ""
    echo "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo "${CYAN}  0luka Chat Control Plane${NC}"
    echo "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Type a command to preview it."
    echo "  Type ${GREEN}confirm${NC} to submit the last preview."
    echo "  Type ${YELLOW}watch${NC} to check task status."
    echo "  Type ${RED}quit${NC} or ${RED}exit${NC} to leave."
    echo ""
    echo "${CYAN}───────────────────────────────────────────────────────${NC}"
    echo ""

    local last_preview_id=""
    local last_task_id=""

    while true; do
        echo -n "${BLUE}0luka>${NC} "
        read -r input

        # Handle empty input
        [[ -z "$input" ]] && continue

        # Handle exit
        case "$input" in
            quit|exit|q)
                echo ""
                echo "${YELLOW}Goodbye!${NC}"
                exit 0
                ;;
            confirm|y|yes)
                if [[ -z "$last_preview_id" ]]; then
                    echo "${RED}No preview to confirm. Enter a command first.${NC}"
                    continue
                fi
                echo "${YELLOW}Confirming...${NC}"
                local confirm_response=$(call_confirm "$last_preview_id")
                local result=$(show_confirm "$confirm_response")
                last_task_id=$(echo "$result" | tail -1)
                last_preview_id=""

                # Auto-watch if confirmed
                if [[ -n "$last_task_id" && "$last_task_id" != "unknown" ]]; then
                    echo ""
                    echo "${YELLOW}Watching task...${NC}"
                    for i in {1..10}; do
                        local watch_response=$(call_watch "$last_task_id")
                        show_watch "$watch_response"

                        local state=$(echo "$watch_response" | jq -r '.state // "unknown"')
                        if [[ "$state" == "done" || "$state" == "failed" ]]; then
                            break
                        fi
                        sleep 2
                    done
                fi
                ;;
            watch|w)
                if [[ -z "$last_task_id" ]]; then
                    echo "${RED}No task to watch. Confirm a task first.${NC}"
                    continue
                fi
                echo "${YELLOW}Watching...${NC}"
                local watch_response=$(call_watch "$last_task_id")
                show_watch "$watch_response"
                ;;
            watch\ *)
                local tid="${input#watch }"
                echo "${YELLOW}Watching task ${tid}...${NC}"
                local watch_response=$(call_watch "$tid")
                show_watch "$watch_response"
                ;;
            status|stats)
                curl -s "${API_BASE}/stats" | jq .
                ;;
            help|h|\?)
                echo ""
                echo "  ${YELLOW}Commands:${NC}"
                echo "    <any text>     Preview as a command"
                echo "    confirm        Submit the last preview"
                echo "    watch [id]     Watch task status"
                echo "    status         Show session stats"
                echo "    quit           Exit"
                echo ""
                ;;
            *)
                # Preview the input
                echo "${YELLOW}Previewing...${NC}"
                local preview_response=$(call_preview "$input")
                local result=$(show_preview "$preview_response")
                last_preview_id=$(echo "$result" | tail -1)

                if [[ -n "$last_preview_id" && "$last_preview_id" != "unknown" ]]; then
                    echo "  Type ${GREEN}confirm${NC} to submit, or enter a new command."
                    echo ""
                fi
                ;;
        esac
    done
}

# ============================================================
# Main
# ============================================================

main() {
    local cmd="${1:-interactive}"

    case "$cmd" in
        preview)
            if [[ -z "${2:-}" ]]; then
                echo "Usage: chatctl.zsh preview \"your command\""
                exit 1
            fi
            local response=$(call_preview "$2")
            show_preview "$response"
            ;;
        confirm)
            if [[ -z "${2:-}" ]]; then
                echo "Usage: chatctl.zsh confirm <preview_id>"
                exit 1
            fi
            local response=$(call_confirm "$2")
            show_confirm "$response"
            ;;
        watch)
            if [[ -z "${2:-}" ]]; then
                echo "Usage: chatctl.zsh watch <task_id>"
                exit 1
            fi
            local response=$(call_watch "$2")
            show_watch "$response"
            ;;
        interactive|chat|i)
            run_interactive
            ;;
        help|--help|-h)
            echo "Usage: chatctl.zsh [command]"
            echo ""
            echo "Commands:"
            echo "  preview \"cmd\"     Preview a command"
            echo "  confirm <id>      Confirm preview"
            echo "  watch <id>        Watch task"
            echo "  interactive       Interactive mode (default)"
            echo ""
            ;;
        *)
            # Assume it's a command to preview
            local response=$(call_preview "$cmd")
            show_preview "$response"
            ;;
    esac
}

main "$@"
