#!/usr/bin/env bash
# Research only. Run once in the disposable exact historical snapshot.
set -u
ROOT=/home/hsa/projects/list_app-night-s3-review
SNAP=/home/hsa/projects/list_app-night-s3-review-snapshot
EVIDENCE="$ROOT/docs/background/reminders-s3-scope-review-evidence"
cd "$SNAP" || exit 91
if test -e .env; then printf 'Unsafe snapshot: .env exists\n'; exit 92; fi
{
  printf 'Exact parent: 216b2eabfd25b6467d64e97906601879ad723084\n'
  printf 'No source changes; no .env; shared pre-existing environment; no sync/install.\n'
  printf 'Selected tests: generation, scheduler, strip claims, external restore state.\n'
  printf 'Tests use :memory: plus pytest temporary SQLite/files; no listening server/provider.\n'
  date -u
  jj --ignore-working-copy status
  env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 TZ=UTC \
    PYTHON_DOTENV_DISABLED=1 DB_PATH=:memory: \
    APP_PASSWORD=test-only-s3-scope-research APP_RELOAD=false \
    REMINDERS_ENABLED=false PUSH_ENABLED=false \
    REMINDER_RESTORE_STATE_PATH="$EVIDENCE/historical-temp/missing-restore-guard" \
    UV_PROJECT_ENVIRONMENT=/home/hsa/projects/list_app/.venv \
    uv run --offline --no-sync pytest -q -n 0 \
    --basetemp "$EVIDENCE/historical-temp" \
    tests/test_reminders_generation.py tests/test_reminders_scheduler.py \
    tests/test_reminders_strip_claim.py tests/test_reminders_restore_state.py
  result=$?
  printf '%s\n' "$result" > "$EVIDENCE/historical-check.exit"
  jj --ignore-working-copy status
  date -u
  printf 'CHECK EXIT: %s\n' "$result"
} > "$EVIDENCE/historical-check.log" 2>&1
printf 'Historical snapshot check complete. Read historical-check.log and .exit.\n'
