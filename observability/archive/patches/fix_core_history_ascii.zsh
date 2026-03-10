#!/usr/bin/env zsh
set -euo pipefail

cd "$HOME/02luka"

# Targets: generators that write Core History headers/lines
targets=(
  "tools/build_core_history.zsh"
  "tools/core_history_sync.zsh"
)

ts="$(date +"%Y%m%d_%H%M%S")"

for f in "${targets[@]}"; do
  [[ -f "$f" ]] || continue
  cp -p "$f" "$f.bak_${ts}"

  python3 - <<PY
from pathlib import Path

p = Path("$f")
s = p.read_text(encoding="utf-8")

# Force ASCII-only punctuation in outputs (prevents any mojibake ever showing up again)
repl = {
  "—": " - ",
  "–": " - ",
  "→": " -> ",
  # common mojibake sequences that sometimes get baked into files
  "‚Äî": " - ",
  "â€”": " - ",
  "¬∑": " -> ",
  "â†’": " -> ",
}

for k,v in repl.items():
  s = s.replace(k, v)

p.write_text(s, encoding="utf-8")
print(f"patched: {p}")
PY
done

# Rebuild core history (this should rewrite g/core_history/latest.md etc.)
if [[ -f tools/build_core_history.zsh ]]; then
  zsh tools/build_core_history.zsh
elif [[ -f tools/core_history_sync.zsh ]]; then
  zsh tools/core_history_sync.zsh --run
else
  echo "No core history builder found."
  exit 1
fi

# Show the key lines so you can confirm mojibake is gone
echo "---- latest.md (head) ----"
sed -n '1,12p' g/core_history/latest.md
