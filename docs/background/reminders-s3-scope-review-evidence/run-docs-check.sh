#!/usr/bin/env bash
# Documentation build only. Background reports are excluded from site rendering.
set -u
cd /home/hsa/projects/list_app-night-s3-review || exit 91
EVIDENCE=docs/background/reminders-s3-scope-review-evidence
{
  date -u
  UV_PROJECT_ENVIRONMENT=/home/hsa/projects/list_app/.venv \
    uv run --offline --no-sync python scripts/build_docs_site.py
  result=$?
  printf '%s\n' "$result" > "$EVIDENCE/docs-build.exit"
  date -u
  printf 'DOCS BUILD EXIT: %s\n' "$result"
} > "$EVIDENCE/docs-build.log" 2>&1
printf 'Documentation build complete. Read docs-build.log and .exit.\n'
