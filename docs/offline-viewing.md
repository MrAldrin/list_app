# Offline viewing

The app can show saved data without a network. It is read-only. Offline editing
is not supported. Status: built and tested locally, awaiting owner review (see
the [backlog](../plans/backlog.md)). Evidence is in the
[validation record](background/offline-viewing-validation.md).

## What works offline

- A service worker (`/service-worker.js`) stores one complete app version. A new
  version installs in the background and takes over only when old tabs close.
- `/admin` and `/app` navigations always go to the network.
- After a successful online load, the browser (IndexedDB) keeps a snapshot of
  the room, its lists, each private list and each share link you opened.
- Offline, these pages show the snapshot with a "saved view" notice: room, room
  list, private list (including the old URL shape) and share pages.
- All edit controls are disabled, and the data layer refuses writes too.
- Typing in the Add field filters the list, only in saved views. Online it only
  gives suggestions.
- If the network is gone, the start page can reopen the last room.

## Errors

- "Connect to load..." means a network failure and no snapshot.
- Any other failure says "Could not load this ...".
- Network errors and 5xx answers keep the snapshot. A 401 or a confirmed
  invalid share link clears it.

## Reconnect

On reconnect, when the app returns to the foreground (`visibilitychange`, or a
restored `pageshow`), it revalidates before editing. One check runs at a time.
Other devices' edits, deletes and password resets then show up.

## Privacy and logout

- Logout stops the live feed, stores a local sign-out marker, then clears saved
  data and shows the password prompt. The marker survives a reload.
- If local clearing takes more than 5 s, the result is `local_clear_unconfirmed`
  and the app says so.
- Snapshots hold server state only. A room snapshot never authorizes a share
  view, and the reverse.
- Logout in one tab clears the others. Without Web Locks (plain HTTP on a LAN),
  logout is local only; use HTTPS or localhost.
