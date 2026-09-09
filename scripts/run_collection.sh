#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_id="$(date -u +%Y-%m-%d_%H%MZ_weekly)"

: "${GOOGLE_APPLICATION_CREDENTIALS:?Set this to the server-only service-account key path}"

mkdir -p "${repo_root}/collections"

exec flock -n "/tmp/menutracker-${USER}.lock" \
  docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "${repo_root}/collections:/app/collections" \
  -v "${GOOGLE_APPLICATION_CREDENTIALS}:/app/creds.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/creds.json \
  menutracker Master_Compile.py \
  "${run_id}_collection" \
  --evidence-dir "collections/${run_id}_evidence" \
  --archive-gcs "gs://intake24-menutracker-collections"
