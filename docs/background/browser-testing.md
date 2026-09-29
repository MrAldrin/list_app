# Real-browser tests: scenarios and measurements

Supporting detail for [real-browser tests](../browser-testing.md). That page
is the source for how to run the suite and what it covers today.

## Public-sharing scenarios

Each runs in both Chromium and Firefox:

1. Room login and list creation; old slug URL denied to a visitor; Share link
   opens without a password; changes appear live in the other session; revoked
   edits are rejected; the new link works; a real server restart keeps the new
   link and remembered room access through `/`.
2. An open public Undo cannot restore a deleted item after reset; public access
   does not grant room entry.
3. An open public Add cannot write after reset, while an open room tab stays
   editable without reloading.
4. Cancelling the reset keeps the original link working.
5. Truncated and wrong tokens show neither contents nor editing controls.
6. A visitor can add and remove list tags but has no rename control; a room
   member does.
7. An open public tab sends a tag edit after reset and it is not saved; the new
   link allows a new tag edit.
8. An open room rename dialog saves after a password change revoked access; the
   name stays unchanged.

## Design choices

- **Delayed WebSocket updates.** For stale-action tests, Playwright holds back
  server-to-browser updates during the reset or deletion. The stale tab sends
  real Socket.IO events, then updates resume and the test checks the saved
  data. Without this, a test would only see a button disappear.
- **Matching the event to the control.** Deletion tests check that the outgoing
  NiceGUI event came from the clicked control (and the toggle value or tag Enter
  key), not just any event.
- **Seeded setup.** Seven sharing scenarios and the deletion cases seed their
  disposable list directly; they still log in and use the real Share dialog.
  The two restart journeys create lists end-to-end.
- **Native sharing disabled** so the copy dialog is used and the URL can be read
  from it.
- **Restart tests** keep only that test's database, secret, browser contexts,
  storage and Service Workers. Pages leave for `about:blank` before shutdown.
  A separate test keeps a room tab open during the restart; the app reloads it
  and it must show a visitor's new item without the test reloading it. That
  does not prove a reload-free reconnection.
- **Teardown** tries remaining screenshots, traces and context closure even if
  one step fails, and reports the diagnostic error.

## Deleted-list matrix

The original 28 cases were cut to 16. All six stale actions run in both
engines, with room and public roles alternated per engine; the four
room-deletion cases keep both roles in both engines. A bug that only appears in
a dropped role/engine pair could be missed. Coverage map and benchmark:
[test-suite speed plan](../../plans/test-suite-speed.md#follow-up-reduce-role-by-engine-crossings-2026-09-28).

## Past measurements (one machine)

- 2026-09-23: 16 cases passed with Playwright 1.63.0, Chromium 153.0.8010.12,
  Firefox 155.0.
- Four workers: 14 clean 50-case runs (70.5–75.1 s) after restart and
  screenshot fixes, then nine clean 52-case runs (74.8–77.7 s).
- 40-case suite after the matrix cut: three runs at 58.5–59.1 s.
- Earlier four-worker runs failed in teardown; see the
  [test-suite speed plan](../../plans/test-suite-speed.md) for fixes.
- Seeding the sharing setup gave a small gain; see
  [measurements](../../plans/test-suite-speed.md#follow-up-public-sharing-setup-2026-09-28).

Parallel stability on other machines has not been measured.
