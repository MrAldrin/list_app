# Offline editing: details

Supporting detail for [offline use](../offline-viewing.md), which gives the
current behavior. Rules R1-R13 and the decisions are in the
[offline editing plan](../../plans/offline-editing.md). This page explains the
mechanics behind them.

## Saved views

- A service worker (`/service-worker.js`) stores one complete app version. A new
  version installs in the background and takes over only when old tabs close.
- `/admin` and `/app` navigations always go to the network.
- After a successful online load, the browser (IndexedDB, `listr-snapshots`)
  keeps a snapshot of the room, its lists, each private list and each share link
  opened. Snapshots hold server state only. A room snapshot never authorizes a
  share view, and the reverse.
- Offline, these pages show the snapshot: room, room list, private list
  (including the old URL shape) and share pages.
- The page turns offline at once when the phone reports no network, or when the
  live connection has been down for 10 seconds.
- A snapshot not saved for 30 days is dropped when a room or share opens. The
  room or share you open keeps its own.
- Typing in the Add field filters the list, only in saved views. Online it only
  gives suggestions.
- If the network is gone, the start page can reopen the last room.
- The offline notice is decided by one check, `RoomStore.showsOfflineNotice`.
  While it shows, it is the only connection message. The "Reconnecting…" pill and
  the "Could not load the latest changes." box (network errors only) are hidden.
  Server errors still show the error box.

## Queue storage

- One IndexedDB database, `listr-queue`, one object store, one record per room
  (`room:<slug>`) or share link (`share:<token>`). Each change is one
  read-modify-write transaction, so two tabs cannot lose an entry.
  See `frontend/src/lib/data/queue-storage.ts`.
- Each entry keeps the op JSON, the time it was made, a format number and a
  state (`pending` or `approved` after a hold). `sent` is set before the request
  goes out, so after a reload an op may be shown as uncertain.
- Without IndexedDB, or after a storage failure, entries live in memory and are
  lost on reload. The page asks the browser for persistent storage once.
- Web Locks let one tab send a room's queue at a time. Without Web Locks, the
  queue still works, and the op id keeps a double send harmless.

## Sending waiting changes

- Sent in order, one at a time, after the app checks access and reads the
  changes feed. Edits made during that check are queued too.
- A change to a row the page already changed uses the row's new version
  (R3). A change made after someone else changed the row is refused with
  `changed_meanwhile` unless the stored value already matches (R2).
- Deltas (quantity) are never refused for a changed row (R1).
- An item added offline gets its own id. If the server already has an active
  item of that name, the answer names it (`duplicate_active`, R6). Later changes
  to the new item go to the existing one.
- A rejection of a waiting change goes to the Not saved list (below). A
  rejection of an online change that answered within 10 seconds is a toast.
  "Waited" means: made offline, loaded from storage, or answered more than
  10 seconds after it was made.
- Held (over 30 days) and unreadable entries block later entries of the same
  room until they are sent or discarded. This keeps the order.
- Entries written by a newer format stay in storage and are not sent. They can
  only be discarded (R13).

## Not saved

- The list is in memory. Dismiss, or Dismiss all, removes entries.
- "Save mine anyway" (only for `changed_meanwhile`) sends the same change again,
  with the row's current version as `base_seq`.
- The same sheet lists held changes (Send all, Discard each) and unreadable
  changes (Discard each).

## Access gone (R9)

- A password change or a share link reset is seen on the next access check.
  Waiting changes then stay on the device and show "can't be sent".
- A room has "Sign in": the password prompt sends the waiting changes once
  access is confirmed. A reset share link allows only Discard all.

## New versions

- A tab that no worker controls can still ask for a lazy chunk of the replaced
  build, which is gone. SvelteKit sees the new `_app/version.json` and opens the
  address again (a full page load), for link clicks and the first load.
- `lib/stale-build.ts` covers the first load when the version file is
  unchanged: on Vite's `vite:preloadError` it reloads once. Offline it does
  nothing. A second failure within 60 s, or no usable session storage, shows
  the normal error page instead of reloading.
- A worker-controlled tab keeps its complete cached version.
- The worker downloads a new version in the background. It only reaches
  "waiting" once every file is stored. When the app opens, or comes back to the
  screen, and a version waits, the page asks it to take over
  (`lib/service-worker.ts`), also offline. The takeover waits while the page
  holds unsent changes or typed text.
- When an API answer has another `X-Api-Version` than the page expects, the
  data layer stops all writes (reason `incompatible_version`, also in the Api
  client for admin and other calls; sign-out still works). Queued ops keep their
  `op_id` and are not retried or dropped. They stay in storage, so a reload keeps
  them.
- The notice (`ui/UpdateNotice.svelte`) says "Reloading now will lose it" only
  for changes that live in memory (`compat.unsavedWrites`). Changes in storage
  are shown as saved on the phone and not sent yet.
- Reload first fetches the newest version and lets it take over, so it does not
  load the old saved copy again. Reading continues.
- Answers without the header are treated as compatible, because proxy and
  maintenance pages during a deploy have none. See [API version](../api.md#api-version).

## Errors

- "Connect to load..." means a network failure and no snapshot.
- Any other failure says "Could not load this ...".
- Network errors and 5xx answers keep the snapshot. A 401 or a confirmed invalid
  share link clears it.

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
- Logout in one tab clears the others. Without Web Locks (plain HTTP on a LAN),
  logout is local only; use HTTPS or localhost.
