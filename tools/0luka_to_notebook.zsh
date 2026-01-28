#!/bin/zsh
# 0luka Knowledge Collator v1.0
# Purpose: Collate 0luka Intelligence for NotebookLM Ingestion

OUTPUT_DIR="$HOME/0luka/observability/notebook_ingest"
mkdir -p "$OUTPUT_DIR"

echo "📦 Collating 0luka Intelligence..."

# 1. Protocols & Culture
echo "   - Copying Protocols..."
cat core/governance/agent_culture.md > "$OUTPUT_DIR/CORE_PROTOCOL.md"
# Append other governance docs if they exist
if ls core/governance/*.md >/dev/null 2>&1; then
    cp core/governance/*.md "$OUTPUT_DIR/"
fi
# Copy Manuals if they exist
if [ -d "g/manuals" ]; then
    cp g/manuals/*.md "$OUTPUT_DIR/" 2>/dev/null
fi

# 2. Logs (Recent History)
echo "   - Extracting Recent Logs..."
if [ -f "observability/stl/ledger/global_beacon.jsonl" ]; then
    tail -n 100 observability/stl/ledger/global_beacon.jsonl > "$OUTPUT_DIR/RECENT_BEACON.json"
fi

# 3. Planner Decisions (Plans)
echo "   - Collecting Recent Plans..."
# Copy last 5 generated plans as decision examples
ls -t interface/plans/*.json 2>/dev/null | head -n 5 | xargs -I {} cp {} "$OUTPUT_DIR/"

# 4. Master Prompt (Ensure it stays there)
if [ ! -f "$OUTPUT_DIR/MASTER_PROMPT.md" ]; then
    echo "⚠️  MASTER_PROMPT.md missing. Please restore it."
fi

echo "✅ Done! Files are ready in: $OUTPUT_DIR"
echo "👉 Drag & Drop these files into NotebookLM."
