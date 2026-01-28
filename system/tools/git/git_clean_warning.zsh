#!/usr/bin/env zsh
# Git Clean Warning - Shows warning before allowing dangerous git clean

ROOT="${ROOT:-${LUKA_SOT:-${HOME}/0luka}}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SAFE_SCRIPT="${SCRIPT_DIR}/safe_git_clean.zsh"

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo ""
echo "${RED}WARNING: Direct 'git clean' is DANGEROUS!${NC}"
echo ""
echo "${YELLOW}You just tried to run: git clean $*${NC}"
echo ""
echo "This command can PERMANENTLY DELETE:"
echo "  - Untracked files"
echo "  - Workspace data"
echo "  - Tools and scripts"
echo "  - Critical artifacts"
echo ""
echo "${GREEN}SAFE ALTERNATIVE:${NC}"
echo ""
echo "  # 1. Preview what will be deleted (ALWAYS DO THIS FIRST):"
echo "  ${GREEN}zsh ${SAFE_SCRIPT} -n${NC}"
echo ""
echo "  # 2. After reviewing, delete only ignored files:"
echo "  ${GREEN}zsh ${SAFE_SCRIPT} -f${NC}"
echo ""
echo "${YELLOW}If you REALLY want to run direct git clean:${NC}"
echo "  /usr/bin/git clean $*"
echo ""
echo "${RED}Aborted to protect your data.${NC}"
echo ""
exit 1
