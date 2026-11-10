# A28 and UI combined source gates

**Result: requested joined component gates passed.** Verification root `/home/hsa/projects/tmp-reminders-s3-verify`; empty working child `zzrmzpqw/6458b68d`, parent `vtlptvvs/8743a470`, a clean join with parents reviewed UI `6d8728e1` and approved A28 `a547dadc`. Before and after every gate, `jj diff --from 8743a470 --to @ --summary` and `git diff --cached --name-status` were empty. Final `jj status` is clean. The five focused browser test files are byte-identical between `6d8728e1` and `8743a470` as checked by `jj diff`; the tests were not edited. No tracked edits, staging, index cleanup, history/bookmark changes, installs or dependency changes were made.

Existing node_modules and venv were used; Node v24.15.0, npm 11.12.1, uv 0.13.6, `UV_NO_SYNC=1`. Gates ran sequentially; full logs, commands and exit codes, per-command before/after source/index checks, disk records and scripts are retained in ignored `/home/hsa/projects/tmp-reminders-s3-verify/.pi/a28-ui-combined/`. Previous evidence was not overwritten.

| Directory | Command | Result |
|---|---|---|
| frontend | `npm run format` | passed, no tracked diff |
| frontend | `npm run lint` | passed |
| frontend | `npm run check` | passed, 0 errors and 0 warnings |
| frontend | `npm run test` | passed; 64 files, 1206 tests, no skips reported |
| frontend | `npm run build` | passed; ignored build completed before Python and browser tests |
| root | `uv run ruff format .` | passed; 335 files unchanged |
| root | `uv run ruff check --fix .` | passed, no tracked diff |
| root | `uv run pytest -q --basetemp=/home/hsa/projects/tmp-reminders-s3-verify/.pi/a28-ui-combined/python-tmp` | passed; 2580 passed in 81.19s, zero skips |
| root | `uv run ruff format --check .` | passed; 335 files already formatted |
| root | `uv run ruff check .` | passed |
| root | `uv run ty check` | passed |
| root | `TZ=UTC timeout 1800s uv run pytest -q -n4 browser_tests/test_svelte_reminder_strip.py browser_tests/test_svelte_history_actions.py browser_tests/test_svelte_reminder_history.py browser_tests/test_svelte_private_reminders.py browser_tests/test_svelte_policy_editor.py --basetemp=/home/hsa/projects/tmp-reminders-s3-verify/.pi/a28-ui-combined/matrix-tmp` | passed; 300 passed in 492.13s, zero skips |

No gate failed, timed out or skipped; the nine build-absence skips from standalone A28 did not occur. Full pytest finished and the parent received its counts and disk update before browser start. Both large runs were monitored at 10-second intervals against an 800 MiB stop threshold. Before browser start free disk was 2,295,799,808 bytes; lowest recorded browser value was 1,188,564,992 bytes, above the stop threshold. After cleanup free disk was 2,173,161,472 bytes; other concurrent usage can affect values.

Per standing permission, **only these own fully passed basetemps** were deleted after their durable outside logs and summaries existed:
- `/home/hsa/projects/tmp-reminders-s3-verify/.pi/a28-ui-combined/python-tmp` — 315,413,942 apparent bytes; 2580 passed; `pytest.log` and `python-cleanup.log` retained.
- `/home/hsa/projects/tmp-reminders-s3-verify/.pi/a28-ui-combined/matrix-tmp` — 652,076,958 apparent bytes; 300 passed; `browser-matrix.log` and `matrix-cleanup.log` retained. Its success traces/screenshots were removed with the basetemp; no failure artifacts existed to preserve.

Final process inspection found no matching own fixture uvicorn/pytest processes; a pre-existing unrelated port-8080 preview process in `/home/hsa/projects/tmp-reminder-delivery` was left untouched. No provider or production operations were performed.

**Scope limit:** this is the approved A28/UI joined component and focused browser seam validation, not whole S3, P acceptance, full-browser, phone, process-restart, owner or production approval. Historical S3 unknown cases and P f17 WebKit 387-pass/1-error remain open; this result neither resolves nor classifies them. No full-suite rerun or browser retry was performed.
