#!/usr/bin/env zsh
set -euo pipefail
IFS=$'\n\t'

ROOT="${HOME}/0luka"
HDR="${ROOT}/skills/_shared/header_contract.zsh"

[[ -d "${ROOT}/skills" ]] || { print -r -- "ERR: missing ${ROOT}/skills"; exit 2; }

# 1) Rewrite header_contract.zsh with valid ZSH identifiers
cat > "${HDR}" <<'EOF'
#!/usr/bin/env zsh
# -----------------------------------------------------------------------------
# 0luka Shared Header Contract (v1.1) — ZSH-safe identifiers
# -----------------------------------------------------------------------------
set -euo pipefail
IFS=$'\n\t'

# Resolve paths (absolute)
OLUKA_HEADER_PATH="${0:A}"
OLUKA_HEADER_DIR="${OLUKA_HEADER_PATH:h}"          # .../skills/_shared
OLUKA_SKILLS_DIR="${OLUKA_HEADER_DIR:h}"          # .../skills
OLUKA_ROOT="${OLUKA_SKILLS_DIR:h}"                # .../0luka

# Default dirs (can be overridden by env before sourcing)
: "${OLUKA_STATE_DIR:=${OLUKA_ROOT}/.state}"
: "${OLUKA_TELEMETRY_DIR:=${OLUKA_ROOT}/observability/telemetry}"
: "${OLUKA_LOG_DIR:=${OLUKA_ROOT}/observability/logs}"

mkdir -p "${OLUKA_STATE_DIR}" "${OLUKA_TELEMETRY_DIR}" "${OLUKA_LOG_DIR}" 2>/dev/null || true

oluka_ts_utc() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

log_info() { print -r -- "[INFO] $*"; }
log_warn() { print -r -- "[WARN] $*" >&2; }
log_err()  { print -r -- "[ERR ] $*" >&2; }

cleanup() { :; }
trap cleanup EXIT INT TERM
# -----------------------------------------------------------------------------
EOF

chmod +x "${HDR}"

# 2) Bulk replace invalid identifiers in all skill executables
#    0LUKA_  -> OLUKA_
#    0luka_  -> oluka_
for f in "${ROOT}"/skills/**/*.zsh; do
  [[ -f "$f" ]] || continue
  perl -0777 -pe 's/\b0LUKA_/OLUKA_/g; s/\b0luka_/oluka_/g' "$f" > "${f}.tmp"
  mv -f "${f}.tmp" "$f"
done

# 3) Ensure executables still executable
chmod +x "${ROOT}/skills/liam/liam.zsh" "${ROOT}/skills/codex/codex.zsh" "${ROOT}/skills/antigravity/antigravity.zsh" || true

print -r -- "OK: patched header + skill executables"
print -r -- "  ${HDR}"
print -r -- "  ${ROOT}/skills/liam/liam.zsh"
print -r -- "  ${ROOT}/skills/codex/codex.zsh"
print -r -- "  ${ROOT}/skills/antigravity/antigravity.zsh"
