# Real-browser tests

The opt-in `browser_tests/` suite uses Playwright to drive real Chromium and
Firefox browsers against a separate ListR server process. Each scenario gets
independent **room-member and public-visitor browser contexts**: cookies,
localStorage, and server-side browser sessions are not shared between users.
These are real browser engines, not mocked NiceGUI handlers or desktop clicking.

## Run

```bash
uv sync
uv run playwright install chromium firefox
uv run pytest browser_tests -q -n 0
```

Playwright downloads its own compatible browsers; installed desktop Chrome or
Firefox are not required. On supported Linux distributions, missing OS libraries
can be installed with `uv run playwright install --with-deps chromium firefox`
(this may require administrator privileges). Do not silently skip tests when a
browser is unavailable.

Run a smaller subset while debugging:

```bash
uv run pytest browser_tests -q -n 0 -k chromium
uv run pytest browser_tests -q -n 0 -k restart
```

The default `uv run pytest -q` still runs the fast tests under `tests/`, without
requiring browser downloads. Browser tests are separate because they launch real
processes and must not inherit the unit suite's in-memory database fixtures.
Use `-n 0` to avoid launching many browsers at once.

## Isolation and diagnostics

- Every test starts a server on a dynamically selected **loopback-only** port.
- Database, NiceGUI storage, working directory, logs, screenshots, and traces are
  in pytest's temporary directory, not the repository.
- Test-only passwords and a fresh signing secret override local credentials;
  `.env` loading is disabled and inherited NiceGUI storage/Redis settings are
  removed. No developer/production database is read or copied.
- Restart tests preserve only that test's database, secret, and browser storage.
- The fixture terminates the server and closes browser contexts, including on
  failure. Server tracebacks and unhandled browser JavaScript errors fail tests.
- Temporary `server.log`, `member-trace.zip`, `visitor-trace.zip`, and screenshots
  help explain failures. Pytest displays the temporary path in failure output.
  Inspect a trace with `uv run playwright show-trace /path/to/member-trace.zip`.
  These artifacts contain disposable test credentials/data; never use this
  harness against production or publish traces from real user sessions.

## Verified coverage

Local verification (2026-09-23): **16 browser cases passed** with Playwright
1.63.0, Chromium 153.0.8010.12, and Firefox 155.0. The 292-test fast suite and
Ruff formatting/lint checks also passed. The existing Starlette/httpx deprecation
warning remains unrelated to this suite.

The suite has eight scenarios, each run in both browser engines:

1. Room login and list creation; legacy URL denied to a visitor; canonical Share
   link opens without a password; changes appear live in the other session;
   revoked edits are rejected; replacement links work; a real server restart
   preserves the new link and remembered room access through `/`.
2. An already-open public Undo action cannot restore a deleted item after reset;
   public access does not grant room entry.
3. An already-open public Add action cannot write after reset, while an existing
   room-authorized tab remains editable without reloading.
4. Cancelling the reset confirmation preserves the original link and its access.
5. Truncated and incorrect tokens expose neither list contents nor editing UI.
6. A public visitor can add and remove list tags with persisted changes, but sees
   no list-rename control; a room member can access the rename control.
7. An already-open public tab sends a tag edit after reset but cannot persist it;
   the replacement link allows a new tag edit.
8. An already-open room rename dialog sends Save after a password change revokes
   its room grant; the list name remains unchanged.

For stale edit/add/undo/tag and rename scenarios, Playwright **delays
server-to-browser WebSocket updates** during revocation. The affected tab sends
real Socket.IO events; the suite then resumes updates, waits for a server
round-trip or the rename rejection's navigation, and checks persisted data.
This avoids a weak test that only sees a button disappear.

Native OS sharing is intentionally disabled in test contexts so the copy-dialog
fallback is deterministic. The tests read the generated URL from that dialog;
OS share sheets and system clipboard behavior are not covered here.

## Deleted-list regression checks

Local verification: 28 new Chromium/Firefox cases passed against disposable app
processes. Separate browser sessions keep a room page or public link open while
another session deletes the list. Delayed WebSocket updates ensure the stale page
actually sends add, edit, toggle, quantity, tag, and undo events after deletion.
The room page shows “This list was deleted.” and “Back to room”; the public page
shows the generic message without room navigation. Room deletion also removes
room navigation from either page. These tests check the resulting database has
no deleted list or forbidden write. At that checkpoint, the full browser suite
passed (46 cases), alongside 309 fast tests and Ruff checks. This is automated
local verification, not a manual multi-user or production device check.

## Checked-item visibility checks

Local verification (2026-09-26): 2 Chromium/Firefox cases exercise persisted
list settings from private and public views, immediate/age/recent modes, shared
updates, Add/Search restoration of a hidden item, and 0-day/0-item behavior.
The full browser suite passed (48 cases); the fast suite passed (374 tests),
with Ruff formatting and lint checks clean. The 24-hour cutoff and per-page
timer behavior have unit tests; no browser test waits for a real day to pass.
See [checked-item visibility](checked-item-visibility.md) for current behavior
and the production-verification boundary.

## Remaining boundaries

These are local HTTP checks. They do not verify production HTTPS cookie behavior,
Railway proxy/volume configuration, migration of a copy of the actual production
database, real iPhone/Android installation, or OS-native share sheets. Playwright
Firefox/Chromium are not evidence of Safari compatibility. Continue with the
[deployment and device checks](public-sharing.md#rollout-and-verification).
