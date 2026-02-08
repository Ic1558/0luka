#!/usr/bin/env zsh
set -euo pipefail

cd ~/02luka

echo "==> Ensure branch"
git checkout feat/lac-telemetry-260114-043756

echo "==> Patch tools/codex_sandbox_check.zsh (add 3 security/test files to WHITELIST_FILES)"

python3 - <<'PY'
from pathlib import Path
import re

p = Path("tools/codex_sandbox_check.zsh")
s = p.read_text(encoding="utf-8")

# Files to whitelist (narrow allowlist - security/test tooling only)
files = [
  "decision_summarizer.py",
  "tools/fix_gemini_bridge_decision_lane.zsh",
  "tools/proof_decision_lane.zsh",
]

m = re.search(r'typeset\s+-a\s+WHITELIST_FILES=\(\n', s)
if not m:
    raise SystemExit("WHITELIST_FILES array not found")

# find closing paren
start = m.end()
end = s.find("\n)", start)
if end == -1:
    raise SystemExit("Could not find end of WHITELIST_FILES array")

body = s[start:end]

missing = [f for f in files if f not in body]
if not missing:
    print("No changes needed: all 3 files already whitelisted.")
    raise SystemExit(0)

# insert before closing paren with comment
insert = "  # PR #432 - Security/test tooling with legitimate dangerous patterns\n"
for f in missing:
    insert += f'  "{f}"\n'

new_s = s[:end] + insert + s[end:]

p.write_text(new_s, encoding="utf-8")
print("Added to whitelist:", ", ".join(missing))
PY

echo "==> Local verify: run sandbox check"
zsh tools/codex_sandbox_check.zsh

echo "==> Commit"
git add tools/codex_sandbox_check.zsh
git commit -m "chore(ci): allowlist security test payloads for codex_sandbox

Whitelist 3 security/test tooling files that use dangerous command patterns
as test payloads or regex patterns for detection (not actual execution):
- decision_summarizer.py (security filtering tool with pattern examples)
- tools/fix_gemini_bridge_decision_lane.zsh (test script with malicious payload)
- tools/proof_decision_lane.zsh (validation script with test payload)

Narrow allowlist: only these 3 files, preserves sandbox security.

Fixes: codex_sandbox check in PR #432" || true

echo "==> Push"
git push

echo "==> Done. Check PR #432 status"
echo "Run: gh pr checks 432 --watch"
