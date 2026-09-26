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
no deleted list or forbidden write. The full browser suite passed (46 cases),
alongside 309 fast tests and Ruff checks. This is automated local verification,
not a manual multi-user or production device check.

## Read-only offline viewing checks

Local verification on this change stack: `uv run pytest browser_tests -q -n 0 -x`
passed **48 cases** in Chromium and Firefox; `uv run pytest -q` passed **358**
fast tests and `node --test tests/test_offline_service_worker.test.mjs` passed
**6** service-worker checks. The browser suite includes one offline scenario per
engine: prepare a disposable room on HTTP, verify a full saved snapshot and
service-worker control, drop the connection, reload room and root launch URLs,
inspect the read-only shell (including unvisited lists and checked items),
reject wrong-room content, verify the no-copy state, and refresh after reconnect.
It also checks an aborted IndexedDB write preserves the prior timestamp, a
private-list edit triggers a refresh, and the HTTP cache contains only generic
shell assets. The API tests cover cookie and header grants, revoked/expired or
wrong-room access, bounds, transient DB errors, and the consistency read lock.

The API is `GET /api/offline/rooms/{slug}/snapshot`; it enforces the existing
room grant, allows the existing same-origin HTTP token header when there is no
cookie, and returns a versioned read-only room/list/item JSON. It rejects
snapshots over 200 lists, 5,000 items, or 1 MiB rather than truncating them.
Definitive denial differs from temporary errors. A single versioned IndexedDB
record replaces a whole room snapshot in one transaction. The service worker
caches only generic shell HTML/CSS/JS, and returns a shell on room/root
navigation only for network failure, not for HTTP errors; it does not cache
private HTML, tokens, or API JSON. The shell rechecks authorization on an
online launch. See [installation and privacy limits](home-screen-installation.md#read-only-offline-viewing-on-a-prepared-browser).

Still unverified: HTTPS offline snapshot fetch with copied Secure/HttpOnly
cookies in a real browser, all combinations of revocation/deletion and storage
failure in Playwright, and iPhone/Android installed-app/force-close behavior.
These require dedicated disposable HTTPS/device checks; HTTP fallback tests
cannot establish them.

## Remaining boundaries

These are local HTTP checks. They do not verify production HTTPS cookie behavior,
Railway proxy/volume configuration, migration of a copy of the actual production
database, real iPhone/Android installation, or OS-native share sheets. Playwright
Firefox/Chromium are not evidence of Safari compatibility. Continue with the
[deployment and device checks](public-sharing.md#rollout-and-verification).
