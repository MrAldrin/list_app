# Real-browser tests

`browser_tests/` uses Playwright to run tests in Chromium, Firefox and WebKit
against a separate ListR server. Each test creates separate browser contexts
for room members and public visitors. They do not share cookies, storage or
sessions.

## Run

```bash
uv sync
uv run playwright install chromium firefox webkit
uv run pytest browser_tests -q -n 4
```

- Four workers is the documented local setting for the full suite. Runtime
  depends on the suite and machine; see [current measurements](background/test-suite-review.md).
  Give a worker count explicitly; pytest's default of eight is for the Python
  suite.
- Playwright downloads its own browsers. On Linux, missing system libraries can
  be installed with `uv run playwright install --with-deps chromium firefox webkit`.
- WebKit is the engine used by every iPhone browser. Playwright's Linux WebKit
  is close to Safari but not identical. It is our Safari check. For device
  checks, see the [risk level](scope.md#risk-level).
- The plain `uv run pytest -q` does not run these tests.

Smaller runs while debugging:

```bash
uv run pytest browser_tests -q -n 0 -k chromium
uv run pytest browser_tests -q -n 0 -k restart
uv run pytest browser_tests -q -n 0  # serial
uv run pytest browser_tests -q -k svelte  # Svelte app only
```

## Engine selection

Tests run on all three engines by default. Add `@pytest.mark.chromium_only`
to an individual test to run an approved detailed journey on Chromium only.
The collection hook selects engines before execution; it does not skip cases.
Do not use a module-wide marker or change the default engine list.

The [approved matrix](background/engine-matrix-review-2026-11-08.md) records
which journeys use this opt-in and which engine-specific checks stay on all
three engines. The timed-due server-confirmation test stays on all three
engines until lr-gt2.4 is fixed.

## Test tiers

Run these optional feedback commands from the repository root. They do not
replace the required checks in `AGENTS.md`.

| Command (`uv run python scripts/run_test_tier.py …`) | Selection |
| --- | --- |
| `python` | All Python tests in `tests/` |
| `frontend` | All Vitest tests |
| `fast` | Python, then frontend; a feedback tier, not a per-test speed promise |
| `smoke` | Four critical browser journeys on all existing engines |
| `affected-browser browser_tests/test_svelte_items.py` | Explicit paths or node IDs, Chromium plus engine-independent cases |
| `full` | All Python, frontend and desktop-browser tests, without selection filters |

Use `--collect-only` with any tier to list its selection without test execution.
Frontend collection uses `vitest list`. Commands stop on the first failure and
return its exit code; a failed or incomplete full run is not a full-suite pass.
Unknown or missing affected paths fail rather than selecting nothing. Repeat
paths to select more than one file. The runner does not infer affected files.
Check the wrapper and label logic without test execution with
`uv run python scripts/check_test_tiers.py`. This separate self-check does not
change the existing pytest suite counts.

Android remains a separate relevant-device run in the
[Android guide](android-emulator-testing.md); `full` does not run the emulator.

The runner takes the machine-wide browser lock for browser commands:
`/home/hsa/.local/state/night-loop/list_app/browser.lock`. Do not wrap the runner
in the same lock. For direct pytest browser commands (including collection),
prefix the command with `flock` and this lock path; do the same for Android.
Run only one browser suite
at a time. Install the existing frontend dependencies and browser binaries first;
see setup above and the [Android guide](android-emulator-testing.md).

Pytest labels are additive; default collection, assertions, engine parameters
and existing skips stay unchanged. `tier_fast` labels `tests/`, `tier_full`
labels all collected pytest cases, and `tier_smoke` labels these exact bodies:

- `test_add_restore_check_quantity_edit_and_undo`
- `test_visitor_views_and_edits_by_link_and_reset_stops_it`
- `test_reconnect_needs_validation_and_feed_then_shows_other_devices_changes`
- `test_bell_counts_overdue_and_today_and_groups_the_panel`

Smoke collection must include all four bodies on Chromium, Firefox and WebKit.
Use `-m layer_api`, `layer_database`, `layer_service` or `layer_tool` to filter
Python tests by the inventory's file layer. `layer_python`, `layer_browser` and
`layer_android` identify suites. Frontend layers remain Vitest files, not pytest
markers. A marker does not override pytest's default `tests/` search path;
request `browser_tests` or `android_tests` explicitly for those suites.

For change-based selection, use `uv run python scripts/select_tests.py` and run
the commands it prints. That selector prints commands only.

Before a deploy, run the checks and smoke tier listed in the
[deployment checklist](deployment.md#deployment-checklist). Run the `full` tier
nightly and after broad or shared changes for feedback. The owner reviews the
result and follows up on failures. A full-tier failure does not block a deploy.

Do not add retries, skips, longer timeouts or arbitrary waits to hide failures.

## Isolation

- Each test starts its own server on a random loopback port.
- The database, storage, logs, screenshots and traces live in pytest's temp
  folder. `.env` is ignored and test-only secrets are used. Real databases are
  never touched.
- WebKit uses a separate, disposable persistent profile for each session. Its
  private-mode CacheStorage does not survive page replacement
  ([Playwright #41618](https://github.com/microsoft/playwright/issues/41618)).
  Profiles are deleted after their contexts close. Replacement tabs stay blank
  until the old tab closes: closing WebKit's last tab would exit the browser.
- Server tracebacks and browser JavaScript errors fail the test.
- Servers and browsers are always shut down, even on failure.

## Debugging failures

Pytest prints the temp folder path. It contains `server.log`,
`member-trace.zip`, `visitor-trace.zip` and screenshots. Open a trace with:

```bash
uv run playwright show-trace /path/to/member-trace.zip
```

Traces hold test data only. Never point this harness at production.

## What it covers

- **Public sharing:** room login, Share link without a password, live updates
  between sessions, link reset, rejected edits from old tabs, bad tokens, tag
  edits by visitors, and rename rights.
- **Server restart:** remembered room access and share links survive a restart;
  an open room tab recovers and shows new items.
- **Stale actions:** an open tab that acts after a reset, password change or
  deletion cannot change data. The tests hold back server updates so the stale
  tab really sends its action, then check the database.
- **Checked-item visibility:** all modes, from private and public views, with
  live updates. Day boundaries are covered by unit tests.
- **Theme:** dark mode is in both room and list menus. The theme
  is remembered per browser, not per room, and is applied before the page
  scripts load (no flash). A color theme chosen in Appearance keeps its colors
  in dark mode and after a reload. Every theme's contrast is checked by
  `frontend/src/app-colors.test.ts`.
- **Svelte app (`test_svelte_*.py`):** on a phone-sized screen: start page,
  login and remembered room; list create, rename and delete; items, quantity,
  edit, delete and undo; tags, filter and hide-done; live updates between two
  phones; a list deleted while open; a password change that
  revokes open pages; light and dark mode; names for
  every control and keyboard focus. Toasts stay small and inside the screen,
  and list controls have 44 px tap areas (`test_svelte_tap_targets.py`).
  The mapping is in the
  [port map](background/browser-test-port-map.md).

## Svelte build

The Svelte tests need `frontend/build/`. If it is missing or older than the
frontend sources, the tests run `npm run build` first. Without `npm` on the
`PATH` they fail and ask you to run `npm run build` in `frontend/`.

Scenario-by-scenario detail and past timings are in
[background](background/browser-testing.md).

## Deleted-list regression checks

Another session deletes the list while a room page or public page is open. The
stale page then tries add, edit, toggle, quantity, tag or undo.

- Room page: shows "This list was deleted." and **Back to room**.
- Public page: shows a generic message with no room navigation.
- Room deletion removes room navigation from both.

Each action runs in both engines, with room and public pages split between
them.

## Limits

These are local HTTP tests in Chromium, Firefox and WebKit. They do not cover HTTPS
cookies, Railway, the production database, Safari, real phone installs, or OS
share sheets. For Android, see the
[emulator suite](android-emulator-testing.md).
