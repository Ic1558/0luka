#!/usr/bin/env zsh
set -euo pipefail
OLD="/Users/icmini/LocalProjects/02luka_local_g/g"
NEW="$HOME/02luka"

# รายการไฟล์จากสแกนล่าสุด (เพิ่มได้ตามที่รายงาน)
FILES=(
  "$HOME/02luka/tools/clc_heartbeat_pulse.zsh"
  "$HOME/02luka/tools/ops_snapshot.zsh"
  "$HOME/02luka/tools/wo_local_apply.py"
  "$HOME/02luka/tools/sync_from_gd.sh"
  "$HOME/02luka/tools/services/simple_health_watcher.zsh"
  "$HOME/02luka/tools/services/clc_wo_processor.cjs"
  "$HOME/02luka/tools/gg_wo_router.sh"
  "$HOME/02luka/tools/final_gd_migration.sh"
  "$HOME/02luka/agents/ollama_worker/run_nlp_worker.sh"
  "$HOME/02luka/agents/ollama_worker/code_worker.py"
  "$HOME/02luka/agents/ollama_worker/nlp_worker.py"
)

# เผื่อไฟล์ .bak ที่ยังใช้อยู่จริงในสคริปต์
FILES+=(
  "$HOME/02luka/agents/ollama_worker/code_worker.py.bak"
  "$HOME/02luka/agents/ollama_worker/nlp_worker.py.bak"
)

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "skip $f"; continue; }
  cp -n "$f" "${f}.bak~" || true
  perl -0777 -pe "s|\Q$OLD\E|$NEW|g" "$f" > "${f}.tmp"
  mv "${f}.tmp" "$f"
  echo "✔ patched $f"
done

echo "✅ All tool scripts patched to $NEW"
