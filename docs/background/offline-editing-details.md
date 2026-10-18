# Offline editing: details

Supporting detail for [offline use](../offline-viewing.md), which gives the
current behavior. This page holds the conflict rules (R1-R13), the mechanics
behind them and the decisions. Code comments refer to the rule numbers.

## Conflict rules

Plain idea: **merge what can be merged; refuse a stale overwrite and tell the
user.** Built in steps 6.1-6.4 of Milestone 6 (see the
[Svelte rewrite record](svelte-frontend-rewrite.md)); live since 2026-10-17.

| # | Situation | Rule |
|---|---|---|
| R1 | Two devices change a quantity | Both deltas count (+1 and +1 give +2). |
| R2 | Two devices tick, edit or rename the same row | A set op carries `base_seq`. If the row changed since and the stored value differs, it is rejected (`changed_meanwhile`). If the value already matches, it is applied. |
| R3 | The user's own queued ops on one row | After one is applied, later queued ops on that row move to its new `changed_seq`. |
| R4 | Tag on an item | The op says the wanted state (`active`), so sending it twice is safe. |
| R5 | Edit vs delete | Delete wins. The edit is rejected and shown as not saved. |
| R6 | Add an item someone else added | One item. The answer names it, and later ops on the new item go to it. |
| R7 | Rename a list to a taken name | Rejected (`duplicate_name`). |
| R8 | Hide-done setting, room name | Last write wins. |
| R9 | Access gone while offline | Changes are kept as "can't be sent". Sign in again, or discard. Reset share link: discard only. |
| R10 | Changes older than 30 days | Not sent automatically; the user chooses Send or Discard. The server forgets answers after 30 days. |
| R11 | Browser clears site data | Unsent changes are lost. The app asks for persistent storage. |
| R12 | Two tabs on one device | One tab sends a room's queue (Web Locks). The `op_id` keeps a double send harmless. |
| R13 | New app version while changes wait | Entries have a format number. One the app cannot read stays, discard only. |

A rejection the user just caused online is a toast. One that waited goes to
the Not saved list.

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
  state (`pending`, `approved` after a 30-day hold, or `signout` while awaiting
  the user's choice after sign-out). `sent` is set before the request goes out,
  so after a reload an op may be shown as uncertain. Not-saved rejections are
  stored in the same room-or-share record.
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

- Validated rejection records are stored in the same device-local room-or-share
  queue record. Dismiss, or Dismiss all, removes entries; successful retries do
  too. Each rejection uses its original op ID as a stable storage key, so tabs
  add, update, and dismiss only their own entries without replacing another
  tab's list. A stale update cannot restore a dismissed entry. Rejections are
  not retried automatically.
- "Save mine anyway" (only for `changed_meanwhile`) sends the same change again,
  with the row's current version as `base_seq`. The rejection stays listed until
  the retry succeeds. A second rejection updates the existing entry instead of
  adding a duplicate. If sign-out clears the room while a retry is in flight,
  its later answer still updates or removes the rejection without restoring
  the room view.
- The same sheet lists held changes (Send all, Discard each) and unreadable
  changes (Discard each).

## Access gone (R9)

- A password change or a share link reset is seen on the next access check.
  Waiting changes then stay on the device and show "can't be sent".
- A room has "Sign in". After access is confirmed, changes held by sign-out
  stay in the queue until the user chooses Send or Discard. A reset share link
  allows only Discard all.

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
- Waiting changes stay in this room's device-local queue after sign-out. The
  queue stays held across reloads and is not released by the next sign-in alone.
  Signing out with changes waiting asks first.
- Room delete with changes waiting says they will be discarded. They are
  discarded after the room is deleted.
- Logout in one tab clears the others. Without Web Locks (plain HTTP on a LAN),
  logout is local only; use HTTPS or localhost.

## Decisions

The owner reviewed the rules on 2026-10-17 and kept them all:

- Row-level conflicts, no field-by-field merge. An edit compares every sent
  field, so a +/− on another device conflicts with an open edit dialog.
  "Save mine anyway" resends on the current version.
- Changes stay held after sign-out until the user chooses Send or Discard.
- Not saved entries persist on the device until dismissed or retried. Never
  retried automatically.
- Creating a list stays online-only (see the backlog).
- A held or unreadable entry blocks later entries of the same room on this
  device. Ordinary rejections do not block.
- A tab with waiting changes keeps the old app version until they are sent.
  Offline for days means the old version for days.
- Closing the app within a few milliseconds of a tap can lose that change
  (written to IndexedDB just after). Accepted.
- Sending waits about 10-15 ms for the Web Lock and IndexedDB. A "send first"
  fast path was rejected as too complex.
- Old stored answers keep their shape: a null new field is left out of the
  request hash, so retries from before the deploy still match.
- Deletions are pruned after 90 days (migration 7). A share link's `seq` never
  goes down after pruning (migration 8, `share_seq_floors`). See
  [change tracking](../change-tracking.md).
- Pre-release iPhone tests were waived; automated checks were accepted. Results:
  [release validation](offline-editing-release-validation.md).

## Why a new version switches on open

Found on the iPhone on 2026-10-12. A new service worker took over only after
every copy of the app closed, including Safari tabs. People could stay on the
old version for a long time, and Reload in the update banner could load the old
copy again. That matters most after an API version bump, which blocks writes
until the phone switches. The owner chose to switch on open and on return to
the screen, when no changes wait (2026-10-13).
