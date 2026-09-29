# Real-browser tests

`browser_tests/` uses Playwright to drive real Chromium and Firefox against a
separate ListR server. Each test has separate room-member and public-visitor
browser contexts, so cookies, storage and sessions are not shared.

## Run

```bash
uv sync
uv run playwright install chromium firefox
uv run pytest browser_tests -q -n 4
```

- Four workers is the tested setting for the full suite (about one minute).
  Give a worker count explicitly; pytest's default of eight is for the fast
  suite.
- Playwright downloads its own browsers. On Linux, missing system libraries can
  be installed with `uv run playwright install --with-deps chromium firefox`.
- The plain `uv run pytest -q` does not run these tests.

Smaller runs while debugging:

```bash
uv run pytest browser_tests -q -n 0 -k chromium
uv run pytest browser_tests -q -n 0 -k restart
uv run pytest browser_tests -q -n 0  # serial
```

## Isolation

- Each test starts its own server on a random loopback port.
- The database, storage, logs, screenshots and traces live in pytest's temp
  folder. `.env` is ignored and test-only secrets are used. Real databases are
  never touched.
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
- **Theme:** the theme is remembered per browser, not per room, and is applied
  before the page scripts load (no flash).

Scenario-by-scenario detail and past timings are in
[background](background/browser-testing.md).

## Deleted-list regression checks

Another session deletes the list while a room page or public page is open. The
stale page then tries add, edit, toggle, quantity, tag or undo.

- Room page: shows "This list was deleted." and **Back to room**.
- Public page: shows a generic message with no room navigation.
- Room deletion removes room navigation from both.

Each action runs in both engines, with room and public pages split between
them. Manual multi-user checks on real devices are tracked in the
[backlog](../plans/backlog.md#pending-production-and-device-verification).

## Limits

These are local HTTP tests in Chromium and Firefox. They do not cover HTTPS
cookies, Railway, the production database, Safari, real phone installs, or OS
share sheets. For Android, see the
[emulator suite](android-emulator-testing.md).
