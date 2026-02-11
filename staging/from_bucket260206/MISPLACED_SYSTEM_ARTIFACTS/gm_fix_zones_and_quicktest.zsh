#!/usr/bin/env zsh
set -euo pipefail

print_h(){ echo; echo "=== $1 ==="; }

# --- Resolve SOT (เชื่อถือ ~/.luka_home ถ้ามี) ---
if [[ -f "$HOME/.luka_home" ]]; then
  SOT="$(cat "$HOME/.luka_home")"
else
  SOT="$HOME/LocalProjects/02luka_local_g/g"
fi
BASE_SYM="$HOME/02luka"

print_h "SOT resolve"
echo "SOT = $SOT"
[[ -d "$SOT" ]] || { echo "❌ SOT not found"; exit 1; }

# --- Ensure full zones for all agents ---
agents=(CLC GG GC MARY PAULA)
zones=(inbox ack outbox failed)
for z in "${zones[@]}"; do
  for a in "${agents[@]}"; do
    d="$SOT/bridge/$z/$a"
    mkdir -p "$d"
    : > "$d/.gitkeep"
  done
done
mkdir -p "$SOT/wo/staging" "$SOT/wo/applied" "$SOT/logs/wo_drop_history" "$SOT/reports/sessions"

print_h "Zones presence"
for z in "${zones[@]}"; do
  for a in "${agents[@]}"; do
    d="bridge/$z/$a"
    [[ -d "$SOT/$d" ]] && echo "✅ $d" || echo "❌ $d"
  done
done

# --- Drop a test WO into CLC inbox ---
print_h "Drop test WO"
TS=$(date +%s)
WO="$SOT/bridge/inbox/CLC/WO-$TS-test.json"
cat > "$WO" <<JSON
{"wo_id":"WO-TEST-$TS","action":"echo","args":["quick-health-check"],"origin":"GG","target":"CLC"}
JSON
echo "→ dropped: $WO"

# --- If router exists, run it once (optional) ---
[[ -x "$SOT/../tools/gg_wo_router.sh" ]] && "$SOT/../tools/gg_wo_router.sh" || true

# --- If nothing processed, simulate a minimal "processed" flow (for wiring check only) ---
sleep 1
if [[ ! -e "$SOT/bridge/outbox/CLC/WO-$TS-test.result.json" ]]; then
  print_h "Simulate process (fallback)"
  cp "$WO" "$SOT/bridge/outbox/CLC/WO-$TS-test.result.json"
  echo '{"ok":true,"note":"simulated-processor"}' > "$SOT/bridge/ack/CLC/WO-$TS-test.ack.json"
fi

# --- Snapshot ---
print_h "Bridge snapshot (L2)"
if command -v tree >/dev/null 2>&1; then
  (cd "$SOT/bridge" && tree -L 2 || true)
else
  (cd "$SOT/bridge" && find . -maxdepth 2 -type d -print)
fi

print_h "Inbox CLC list"
ls -l "$SOT/bridge/inbox/CLC/" || true

print_h "Outbox CLC list"
ls -l "$SOT/bridge/outbox/CLC/" || true

print_h "Ack CLC list"
ls -l "$SOT/bridge/ack/CLC/" || true

print_h "Symlink status"
if [[ -L "$BASE_SYM" ]]; then
  echo "• ~/02luka -> $(readlink "$BASE_SYM")"
else
  echo "• ~/02luka is not a symlink"
fi

print_h "Done"
