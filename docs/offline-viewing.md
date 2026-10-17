# Offline use

The app works without a network for saved data. Edits made offline are kept on
the phone and sent when the connection is back. Status: built and tested
locally, awaiting owner review (see the [backlog](../plans/backlog.md)).
Design: [offline editing plan](../plans/offline-editing.md).

## What works offline

- A service worker (`/service-worker.js`) stores one complete app version. A new
  version installs in the background and takes over only when old tabs close.
- `/admin` and `/app` navigations always go to the network.
- After a successful online load, the browser (IndexedDB) keeps a snapshot of
  the room, its lists, each private list and each share link you opened.
- Offline, these pages show the snapshot: room, room list, private list
  (including the old URL shape) and share pages.
- Editing works on those pages: add, tick, quantity, edit, tags, delete and
  undo, hide-done setting, list rename and delete, room rename. The change shows
  at once.
- Needs a connection (the control is disabled, with the text "Needs a
  connection" under the room menu, list menu and Add New List): creating a
  list, password change, room delete, share link show and reset, sign-in,
  sign-out, admin and invitations.
- Edits are kept in IndexedDB (`listr-queue`), one record per room or share
  link. They survive a reload or closing the app. Where IndexedDB is missing,
  they live in memory only.
- The page turns offline at once when the phone reports no network, or when the
  live connection has been down for 10 seconds. Edits keep working.
- A snapshot not saved for 30 days is dropped when a room or share opens. The
  room or share you open keeps its own.
- Typing in the Add field filters the list, only in saved views. Online it only
  gives suggestions.
- If the network is gone, the start page can reopen the last room.

## Sending waiting changes

- Waiting changes go out in order, one at a time, after the app checks access
  and reads the changes feed. The check runs when the app opens, when the
  connection returns (`online` event or live stream back) and when the app comes
  back to the screen. No background sync.
- A change made on a row the page already changed uses the new row version, so
  the page's own changes do not conflict with each other. A change that someone
  else made meanwhile is rejected (`changed_meanwhile`) and nothing is applied.
- An item added offline gets its own id. If the server already has that item on
  the list, later changes to the new item go to the existing one.
- A rejection of a waiting change goes to the Not saved list (below). A quick
  rejection of an online change is still a toast.
- A dot marks each item and list with a change not sent yet.

## Not saved

- A change that waited is refused or fails after it was made offline, loaded
  after a reload, or answered more than 10 seconds after it was made. It does
  not show a toast. The banner "N changes were not saved" opens a sheet that
  says what and why.
- Actions: Dismiss, or Dismiss all. A change refused because someone else
  changed it meanwhile also has "Save mine anyway". That sends the same change
  again, as a new change based on the current version.
- The same sheet lists old changes held for 30 days (Send all, Discard each)
  and changes this version cannot read (Discard each).
- The list is kept in memory: a reload clears it. Refused changes are not sent
  again by a reload.

## Access gone

- When the room password changes, or a share link is reset, while changes
  wait, the banner says "N changes can't be sent." A room has "Sign in": the
  password prompt sends the waiting changes once you sign in. A reset share
  link only allows "Discard all".

## The offline notice

- Text: "Offline — changes are saved on this phone and sent when you're back
  online." Share pages say the same.
- If changes wait, a second line says "N changes waiting to be sent." It counts
  the changes kept on the device.
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
  their `op_id` and are not retried or dropped. They are kept on the device, so
  a reload keeps them. A banner "A new version is available" has a Reload button
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
restored `pageshow`), it revalidates before sending. One check runs at a time.
Other devices' edits, deletes and password resets then show up.

## Privacy and logout

- Logout stops the live feed, stores a local sign-out marker, then clears saved
  data and shows the password prompt. The marker survives a reload.
- If local clearing takes more than 5 s, the result is `local_clear_unconfirmed`
  and the app says so.
- Waiting changes stay on the device after sign-out. They are sent after the
  next sign-in to the same room. Signing out with changes waiting asks first.
- Room delete with changes waiting says they will be discarded. They are
  discarded after the room is deleted.
- Snapshots hold server state only. A room snapshot never authorizes a share
  view, and the reverse.
- Logout in one tab clears the others. Without Web Locks (plain HTTP on a LAN),
  logout is local only; use HTTPS or localhost.
