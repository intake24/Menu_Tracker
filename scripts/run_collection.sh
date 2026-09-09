#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_id="$(date -u +%Y-%m-%d_%H%MZ_weekly)"

: "${GOOGLE_APPLICATION_CREDENTIALS:?Set this to the server-only service-account key path}"

exec flock -n "/tmp/menutracker-${USER}.lock" \
  "${repo_root}/.venv/bin/python" "${repo_root}/Master_Compile.py" \
  "${run_id}_collection" \
  --evidence-dir "${repo_root}/evidence/${run_id}" \
  --archive-gcs "gs://intake24-menutracker-collections"
