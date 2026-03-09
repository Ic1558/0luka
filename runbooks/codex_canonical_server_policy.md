# Codex Canonical Server Policy

## Scope
- Prevent overlapping `codex app-server` instances that cause endpoint ambiguity.
- Applies to local operator workflows that use Codex + Antigravity on the same host.

## Canonical SOT
- Canonical codex binary path:
  - `/Applications/Codex.app/Contents/Resources/codex`
- Non-canonical examples (must not coexist with canonical server):
  - `~/.antigravity/extensions/openai.chatgpt-*/bin/*/codex`

## Deterministic Rule
- Do not auto-discover codex endpoint from dynamic ports (including `587xx`).
- Use process/path identity check via:
  - `tools/ops/check_codex_overlap.zsh`

## Overlap Response
1. Run guard:
   - `tools/ops/check_codex_overlap.zsh`
2. If exit is non-zero, follow guard advice only.
3. Controlled shutdown for non-canonical process:
   - `kill -TERM <pid>`
4. Re-run guard until it returns `exit 0`.

## Rollback
- If canonical process is unavailable after shutdown:
1. Start Codex.app.
2. Re-run guard and verify:
   - `OK: single canonical codex app-server`
3. If workflow requires extension process for a separate task, re-enable extension explicitly after this workflow.

## Evidence References
- Incident class: Codex overlay with Antigravity extension codex server.
- Evidence collection commands:
  - `ps aux | rg -n "Codex\.app|Antigravity|openai\.chatgpt|codex app-server|language_server"`
  - `lsof -nP -iTCP -sTCP:LISTEN | rg -n "codex|Antigravi|language_|587|app-server"`
- Related freeze policy references:
  - `runbooks/safe_restart_protocol_v1.md`
  - `runbooks/freeze_t1_monitoring_lean.md`
