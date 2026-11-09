# Test tier implementation — 9 November 2026

Evidence for `lr-005.1.5`, change `xqlruunp`, based on accepted
`integration` `ltoqrxzw/6d4b0dcb`. No unaccepted matrix, helper or product
repair was copied. Current commands live in [the browser guide](../browser-testing.md#test-tiers).

## Scope

- Added registered tier/layer labels and a collection-only root hook. All 74
  Python file layers match the `lr-005.1.1` inventory. Frontend remains Vitest.
- Added Python, frontend, fast, smoke, explicit affected-Chromium and full
  commands. Full means Python + frontend + every desktop-browser case, as
  narrowed by `lr-4rc`; Android stays a separate relevant-device run.
- Browser commands, including collection, take the machine-wide lock.
  Affected selection excludes only known Firefox/WebKit parameter cases;
  engine-independent and unknown-engine cases remain included.
- Added an explicit self-check, outside default pytest collection. It checks
  command composition, lock wrappers, collection mode, bad paths, first-error
  propagation, successful full dispatch, frontend working directory, default
  engine retention, independent/unknown-engine retention and labels.
- Ruff now treats `conftest` as a first-party import because the root hook
  exists. Its seven browser-file import-order fixes are mechanical. AST
  comparison confirms unchanged imports and unchanged test bodies/assertions.
  No fixtures, engine definitions, skips or assertions changed.

## Collection proof

Compared exact node sets on this same baseline, not counts from the unaccepted
matrix. Default `testpaths` and worker settings are unchanged.

| Suite/selection | Before | After | Result |
| --- | ---: | ---: | --- |
| Default Python | 1,792 | 1,792 | Exact node equality |
| Browser Chromium | 202 | 202 | Exact node equality |
| Browser Firefox | 202 | 202 | Exact node equality |
| Browser WebKit | 202 | 202 | Exact node equality |
| Smoke | — | 12 | Exact four bodies × three engines |
| Affected `browser_tests` | — | 202 | Every Chromium case, no other current cases |

`full --collect-only` collects the same 1,792 Python nodes and all 606 browser
nodes. Its Vitest list equals the separate frontend command's list: 566 listed
body descriptions. Vitest list does not expand all parameterized cases; this
is not a claim of 566 runtime test cases. Frontend source/config is unchanged.
The full command has no marker or engine filter. Existing intentional skips
remain collected.

Sorted-node-set SHA-256 (UTF-8, newline separators, no trailing newline):

- Python: `8c057ceac7d1760699e69cf3aa56b789fe37444efb550a99b7e7eb8950c75798`
- Browser: `17864b9e097b9750476b231d677cf912a4c870a3eab89bf41f12f7233d4846c5`

## Checks and limits

- `uv run ruff format .`, `uv run ruff check --fix .`, final format/check and
  `uv run ty check`: PASS. No unsafe fixes.
- Existing frontend dependency install, `npm run lint`, `npm run build`: PASS.
  npm reported 16 existing audit findings; no dependencies or lockfile changed.
- `uv run pytest -q`: **1,792 passed**, 58.45 s. The build ran first, so the
  nine build-dependent cases did not skip.
- One browser execution, `affected-browser browser_tests`, four workers:
  **162 passed, 40 existing skips**, 192.52 s. Chromium only; no retries,
  extra waits, timeout increases or second browser execution.
- `uv run python scripts/check_test_tiers.py`: PASS. An early private check
  incorrectly treated Python's `-m pytest` as a marker filter; that check was
  corrected. Another ad hoc check used system Python without pytest; it was
  corrected to `uv run python`. Neither was a product/test failure or browser
  rerun. The inventory-layer comparison then passed for all 74 files.
- Independent review 1 (`708be6a3`): PASS, no findings. Browser completion was
  still pending. Parent then aligned full with the plan's separate Android
  rule and added the durable self-check.
- Independent final review 2 (`294412f9`): PASS, no findings, including completed
  runtime evidence. Both reviewers used verified `openai/gpt-6.1-sol:low`.
  Neither reviewer edited files or executed tests.

No full runtime, Firefox/WebKit runtime, frontend runtime or Android execution
is claimed. The known historical frontend/browser failures were not repaired
or relabeled green. This one Chromium result is not a stability or speed claim.
No gate, deploy script, `AGENTS.md`, plan, backlog, shared history, `main` or
`integration` changed. The owner must accept the feature before it becomes
part of the accepted baseline.

Private evidence directory:
`/home/hsa/.local/state/night-loop/list_app/lr-005.1.5/`.
It retains before/after collection, full/smoke/Chromium/Vitest lists, build and
runtime logs, self-check results and the review diff. The completed check pane
`terminal_22` was closed. Keep the task workspace for morning review.
