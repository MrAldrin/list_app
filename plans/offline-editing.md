# Offline editing (Milestone 6)

Lifecycle: tracked

Steps 6.1 to 6.4 of [Milestone 6](svelte-frontend-rewrite.md#milestone-6-offline-editing).
The owner approved building it start to finish (2026-10-16) without a review
of the rules first. The rules below are the lead agent's choices; the owner
reviews them afterwards. Nothing here is deployed; `main` does not move.

Today: offline pages are read-only ([offline viewing](../docs/offline-viewing.md)).
Unsent changes live in memory only and are lost when the app closes.

## Goal

Edit lists without a network (for example, in a shop with no signal). Changes
are kept on the device, survive closing the app, and are sent when the
connection is back. When someone else changed the same thing meanwhile, nothing
is silently lost: the user sees what was not saved.

No user accounts are needed. Room access works as today: the server checks the
room cookie (or share token) when the changes are sent.

## Conflict rules (6.1)

Plain idea: **merge what can be merged; refuse a stale overwrite and tell the
user.**

| # | Situation | Rule | Why |
|---|---|---|---|
| R1 | Two devices change a quantity (+/−) | Both deltas count (+1 and +1 give +2). | Deltas already merge (`item.quantity_delta`). |
| R2 | Two devices tick, untick, edit or rename the same item or list | A "set" op carries `base_seq`, the row's `changed_seq` the device saw. If someone else changed the row since, and the stored value differs from what this op wants, the op is **rejected** with `changed_meanwhile`; nothing changes. If the stored value already equals what the op wants, it is applied (no conflict). | Stops a late tick from undoing a newer untick (the late-write problem in the plan). Checking "already equal" avoids false conflicts when both did the same. |
| R3 | The user's own queued ops on the same row | After an op on a row is applied, the device moves later queued ops on that row to the row's new `changed_seq` (the answer returns it). | Otherwise a tick followed by an edit offline would conflict with itself. |
| R4 | Tag on an item | The op says the wanted state (`item.toggle_tag` gets an optional `active: true/false`). Applied when already in that state. | Two offline toggles of the same tag would cancel out. With a wanted state the op is safe to send twice. |
| R5 | Edit vs delete | **Delete wins.** An edit, tick or tag change on a deleted item or list is rejected (`item_not_found` / `list_unavailable`) and listed as not saved. | Matches today's online rules. Undo is still possible on the deleting device. |
| R6 | Add an item that someone else added meanwhile | Normal add-or-restore rules. A duplicate active item is not an error to show: the answer names the existing item, and the device's later ops on its own new item go to that item instead. Same for `item.add` that restores a checked item. | The item is on the list; that was the intent. |
| R7 | Rename a list to a name that is now taken | Rejected (`duplicate_name`), listed as not saved. | Names stay unique per room. |
| R8 | Hide-done setting, room name | Last write wins (no `base_seq`). | Low value of a conflict message here. |
| R9 | Access gone while offline (password changed, share link reset, room deleted) | Changes are kept and shown as "can't be sent". Sign in again to send them, or discard them. For a share link that was reset, only discard. | Never drop user data silently; never let old access write. |
| R10 | Changes waiting very long | Ops older than 30 days are not sent automatically; the user chooses Send or Discard. | The server only remembers answers for 30 days, so a retry after that could apply a +1 twice. |
| R11 | Storage loss (browser clears site data) | Unsent changes are lost. The app asks for persistent storage (`navigator.storage.persist()`) and shows "N changes saved on this phone only" while any wait. | Cannot be prevented in a web app; the user is told the risk. |
| R12 | Two tabs on one device | One tab at a time sends a room's queue (Web Locks API, `navigator.locks`). The `op_id` keeps a double send harmless anyway. | Keeps order and avoids double work. |
| R13 | A new app version while changes wait | The queue is stored as API op JSON with a format number. A new version reads old entries; one it cannot read stays as "can't be sent" (discard only). | Decision: updates never delete unsent changes. |

Online, a rejection the user just caused still shows as a toast (as today).
A rejection of an op that waited (made offline, or queued more than 10 seconds)
goes to the **Not saved** list instead, so it is not missed.

## What can be done offline

- Room and share pages: add, tick/untick, quantity, edit, tags (item and
  list), delete and undo, hide-done setting, list rename and delete, room
  rename. Share pages use the same store and queue, so they get the same rules.
- **Not offline:** creating a list (it gets its address from the server; see
  [backlog](backlog.md)), password change, room delete, share link reset,
  sign-in and sign-out, admin, invitations. These controls stay disabled with
  a short hint.
- Only lists that have a saved snapshot can be opened offline (as today).

## Server changes

- `item.set_done` and `list.visibility`: no change for visibility (R8).
  `item.set_done` gets optional `base_seq`. `item.edit` and `list.rename`
  start using their `base_seq`. Without `base_seq` (old clients) the last
  write wins, so the API stays compatible (`X-Api-Version` unchanged).
- New rejection code `changed_meanwhile`.
- Applied answers for one-row ops include the row's new `changed_seq` (R3).
- `item.add` rejected as `duplicate_active` includes the existing `item_uid` (R6).
- `item.toggle_tag` accepts optional `active` (R4).
- **Prune `deletions`:** keep 90 days. Each room records the highest pruned
  seq (`rooms.deletions_pruned_seq`). The changes feed sends a full snapshot
  (`full: true`) when `since` is below it. Pruned at startup and once a day, like
  processed ops.
- **Per-list tracking for share links** (decision 147): `deletions` gets a
  `list_uid` column (migration; the item delete trigger fills it). The share
  feed (already a full snapshot) and stream use the list's own highest
  `changed_seq` (list row, its items, its deletions) as their `seq`, so a link holder no longer sees other
  lists' activity and is not woken by it. Share op answers return the same
  per-list `seq`, so the store's overlay and catch-up rules keep working.

## Client changes

- `QueueStorage` in IndexedDB (one store, keyed by room or share token), behind
  the existing interface in `write-queue.ts`. Each entry: op JSON, `at`,
  format number, state.
- Sync on app open, on reconnect and on return to the foreground. No background
  sync.
- The overlay projects all offline ops, including add, edit, restore, rename and
  list delete, so the user sees their change at once.
- Edit controls are enabled offline; the read-only rule is removed for the ops
  above. The offline notice changes to "Offline — changes are saved on this
  phone and sent when you're back online."
- Not-saved list (6.3): a small banner "2 changes were not saved" opens a sheet.
  Each entry says what and why in plain words ("'milk' was deleted by someone
  else"). Actions: Dismiss; for `changed_meanwhile` also "Save mine anyway"
  (resends with the current `base_seq`).
- A small mark on items with unsent changes.

## Steps

Each step is one or more jj changes, with tests. Browser suite once at the end
of each code step.

1. **6.1** This plan.
2. **6.2a** Server: `base_seq` checks, `changed_meanwhile`, row `changed_seq`
   in answers, `active` on toggle_tag, `item_uid` on duplicate add. API docs.
3. **6.2b** Server: prune `deletions` with the reset watermark; per-list share
   tracking (migration).
4. **6.2c** Client: IndexedDB queue storage, Web Locks, format number, 30-day
   hold, persistent-storage request.
5. **6.2d** Client: editing offline (projection of all ops, controls enabled,
   rebase of own ops, uid remap after duplicate add, sync triggers).
6. **6.3** Client: not-saved banner and sheet, unsent marks, notice text.
7. **6.4** Tests: two devices offline on the same list (each rule above), storage
   loss, revoked access while offline, app update with waiting changes,
   reload with waiting changes. Update `docs/offline-viewing.md` (rename to
   offline use), `docs/api.md`, `docs/change-tracking.md`, `ARCHITECTURE.md`.
8. **Gate C** Owner tests on the iPhone, including two devices.

## Progress

- [x] 6.1 Conflict rules (this plan)
- [ ] 6.2a Server conflict checks
- [ ] 6.2b Deletion pruning and per-list share tracking
- [ ] 6.2c Persistent queue
- [ ] 6.2d Offline editing in the client
- [ ] 6.3 Not-saved UI
- [ ] 6.4 Multi-device tests and docs
- [ ] Gate C: owner review on the iPhone
