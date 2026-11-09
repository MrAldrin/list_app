# Change-based selector validation

Task: lr-005.1.6. Baseline: integration `6d4b0dcba76c3dcba2615f84656a3a954bf075fc`.
Worker: `openai/gpt-6.1-sol:low`, session
`01a1c221-39c8-7307-910d-726c1491f41d`.

## Scope

Print-only standard-library selector, separate synthetic unit-test entry point,
and usage guide. No product code, existing tests, configuration, dependencies,
release gates or browser fixtures changed. No acceptance or deployment.
The explicit script, theme and reminder sets come from the lr-005.1.2 map;
other areas use conservative full feedback. The tool makes no minimality claim.

## Checks

- `uv run python scripts/selector_selftest.py`: 8 unittest cases pass.
  Separate from the existing pytest collection; synthetic mapping fixtures.
- Real-tree script/theme/reminder selections resolve to 1/11/14 test files.
- CLI invalid base prints full feedback; `--base @` reports no changes.
- `uv run ruff format .` and `uv run ruff check --fix .`: clean after formatting
  the two new scripts and fixing two import-order issues.
- `uv run pytest -q`: 1,792 passed, 52.90 seconds; frontend built first.
- `uv run ruff format --check .`, `uv run ruff check .`, `uv run ty check`: pass.
- `npm ci`, `npm run build`, `npm run lint` in `frontend/`: pass.
  npm reports 16 dependency audit findings (4 low, 10 moderate, 2 high).
  No dependency repair or version change attempted.
- Existing Python collection: 1,792 before and after; exact node sets equal.
- Existing browser collection: 606 before and after; exact node sets equal.
  Chromium/Firefox/WebKit each retain 202 cases (including parametrized cases).
- One browser execution: `uv run pytest browser_tests -q -n 4 -k chromium`
  under `flock /home/hsa/.local/state/night-loop/list_app/browser.lock`:
  162 passed, 40 existing skips, 193.63 seconds. No retries.
  Browser collection commands also used this lock.

The selector tests do not certify impact completeness. Required checks remain
unchanged. Firefox/WebKit execution and Android were not run for this tool-only
change. Local raw command logs are `/tmp/lr-005.1.6-*`; this report retains the
results without requiring those temporary files.
