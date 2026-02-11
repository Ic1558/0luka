#!/usr/bin/env zsh
set -euo pipefail

# Hybrid Minimal CLS Agent - Bootstrap Script
# Purpose: Set up lightweight task execution framework for OPS-Atomic monitoring

BASE="${HOME}/02luka"
BRIDGE_DIR="${BASE}/bridge"
INBOX_CLC="${BRIDGE_DIR}/inbox/CLC"
INBOX_CLS="${BRIDGE_DIR}/inbox/CLS"
LOGS_DIR="${BASE}/logs"
AGENTS_DIR="${BASE}/agents"

echo "🔧 Setting up Hybrid Minimal CLS Agent..."

# Create required directories
mkdir -p "${INBOX_CLC}" "${INBOX_CLS}" "${LOGS_DIR}" "${AGENTS_DIR}/cls"

# Create minimal CLS agent config
cat > "${AGENTS_DIR}/cls/config.json" <<'CONFIG'
{
  "name": "CLS-Minimal",
  "version": "1.0.0",
  "role": "task-executor",
  "inbox": "~/02luka/bridge/inbox/CLS",
  "logs": "~/02luka/logs",
  "polling_interval": 300,
  "task_types": ["monitor", "report", "alert"],
  "integrations": {
    "discord": true,
    "ops_atomic": true
  }
}
CONFIG

# Create work order processor
cat > "${AGENTS_DIR}/cls/process_wo.sh" <<'PROCESSOR'
#!/usr/bin/env bash
set -euo pipefail

INBOX="${HOME}/02luka/bridge/inbox/CLS"
LOGS="${HOME}/02luka/logs"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)

# Process any pending work orders
for wo in "${INBOX}"/WO-*.md; do
  [[ -f "$wo" ]] || continue
  
  WO_ID=$(basename "$wo" .md)
  LOG_FILE="${LOGS}/${WO_ID}_${TIMESTAMP}.log"
  
  echo "Processing: ${WO_ID}" | tee -a "${LOG_FILE}"
  
  # Extract and execute tasks from work order
  # (Implementation would parse WO and execute specified tasks)
  
  # Archive processed WO
  mv "$wo" "${INBOX}/processed/${WO_ID}_${TIMESTAMP}.md"
  
  echo "Completed: ${WO_ID}" | tee -a "${LOG_FILE}"
done
PROCESSOR

chmod +x "${AGENTS_DIR}/cls/process_wo.sh"

# Create processed directory
mkdir -p "${INBOX_CLS}/processed"

echo "✅ Hybrid Minimal CLS Agent setup complete"
echo ""
echo "📂 Structure created:"
echo "   - Inbox: ${INBOX_CLS}"
echo "   - Logs: ${LOGS_DIR}"
echo "   - Config: ${AGENTS_DIR}/cls/config.json"
echo "   - Processor: ${AGENTS_DIR}/cls/process_wo.sh"
echo ""
echo "🎯 Ready to accept Work Orders"
