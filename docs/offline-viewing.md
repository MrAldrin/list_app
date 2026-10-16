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
- A snapshot not saved for 30 days is dropped when a room or share opens. The
  room or share you open keeps its own.
- Offline, these pages show the snapshot with an offline notice: room, room
  list, private list (including the old URL shape) and share pages.
- All edit controls are disabled, and the data layer refuses writes too.
- The page turns read-only right away when the phone reports no network, or
  when the live connection has been down for 10 seconds. Changes already
  waiting stay queued and are sent after the connection returns.
- Typing in the Add field filters the list, only in saved views. Online it only
  gives suggestions.
- If the network is gone, the start page can reopen the last room.

## The offline notice

- Text: "Offline — showing your lists from 18:05. Editing is back when you're
  online." Share pages say "this list". The time is `HH:MM` for today, else a
  short date and time. Without a usable time, that part is left out.
- If changes wait in memory, a second line says "N changes waiting to be sent."
  They are sent when the connection returns. They live in memory only, so
  closing the app loses them.
- While the notice shows, it is the only connection message. The "Reconnecting…"
  pill and the "Could not load the latest changes." box (network errors only)
  are hidden. Server errors still show the error box.
- One check decides this: `RoomStore.showsOfflineNotice`.

## After a deploy

- A tab that no worker controls can still ask for a lazy chunk of the replaced
  build, which is gone. SvelteKit sees the new `_app/version.json` and opens the
  address again (a full page load), for link clicks and the first load.
- `lib/stale-build.ts` covers the first load when the version file is
  unchanged: on Vite's `vite:preloadError` it reloads once. Offline it does
  nothing. A second failure within 60 s, or no usable session storage, shows
  the normal error page instead of reloading.
- A worker-controlled tab keeps its complete cached version, so it does not hit
  this.
- New versions: the worker downloads a new version in the background. It only
  reaches "waiting" once every file is stored. When the app opens, or comes
  back to the screen, and a version waits, the page tells it to take over
  (`lib/service-worker.ts`), also offline. Every open tab then reloads onto
  it, except a tab with unsent changes or typed text in a field; that tab
  keeps the old version for now. Coming back with no version waiting checks
  for a new one, which takes over on a later open or return.
- When an API answer has another `X-Api-Version` than the page expects, the
  data layer stops all writes (reason `incompatible_version`, also in the
  Api client for admin and other calls; sign-out still works). Queued ops keep
  their `op_id` and are not retried or dropped, but they live in memory, so a
  reload loses them. A banner "A new version is available" has a Reload button
  and says how many changes are not saved yet. The banner never reloads by
  itself. Reload first fetches the newest version and lets it take over, so it
  does not load the old saved copy again. Reading continues.
  Answers without the header are treated as compatible, because proxy and
  maintenance pages during a deploy have none. See
  [API version](api.md#api-version).

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
