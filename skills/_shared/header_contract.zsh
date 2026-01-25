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
