# Offline editing (Milestone 6)

Lifecycle: tracked

Steps 6.1 to 6.4 of [Milestone 6](svelte-frontend-rewrite.md#milestone-6-offline-editing).
The owner approved building it start to finish (2026-10-16) without a review
of the rules first. The rules below are the lead agent's choices; the owner
reviewed them in the decision log. Nothing here is deployed; `main` does not move.

Current behavior: offline editing and a persistent write queue are implemented.
See [offline use](../docs/offline-viewing.md). This workspace is not deployed.

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
  else"). Entries persist in the device-local room queue until dismissed or a
  successful retry; no rejection is retried automatically.
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
8. **Gate C** Pre-release manual iPhone checks (waived by the owner; automated checks accepted).

## Decisions made while building

Historical implementation choices; the owner review decisions below supersede them where stated.

- **Edit conflicts compare all sent fields.** An `item.edit` conflicts when
  name, description or the sent quantity differs from what is stored. So a
  +/− on another device conflicts with an open edit dialog's old quantity.
  The edit dialog keeps the `base_seq` from when it opened.
- **Old answers keep their shape.** A null new field (`base_seq`, `active`) is
  left out of the stored request hash, so retries of ops sent before the
  deploy still match.
- **Initial sign-out behavior (superseded by owner decision 2).** Stored changes
  used to send after the next sign-in. They now remain held until the user
  chooses Send or Discard.
- **Held or unreadable ops block later ops** of the same room until sent or
  discarded, so the order is kept.
- **Deletion pruning** (migration 7) cuts at the newest old record per room,
  so the cut-off is clean even with clock skew.
- **Share seq floor table** (migration 8, `share_seq_floors`): keeps a
  list's share `seq` from going down after pruning, without touching the
  `lists` triggers.
- **API version bump at deploy.** The share `seq` changes meaning (per list,
  usually lower than before). Bump `API_VERSION` (server and client) in the
  deploy that ships this, so old open pages reload instead of misreading the
  lower `seq`.

- **Sending is not instant any more.** Since the stored queue (6.2c), a
  change reaches the server about 10-15 ms later (Web Lock and IndexedDB
  first). A subagent proposed a "send first, lock later" fast path; the lead
  rejected it as too complex for 15 ms. Browser tests now wait for saved data
  (`wait_until`) instead of reading the database at once.
- **Edits queue during an online check too** (not only offline). The queue
  sends only after access and the feed are confirmed.

- **A very quick close can lose the last change.** The change is written to
  IndexedDB a few milliseconds after the tap. Closing the app within that
  time loses it. Accepted.
- **A tab with waiting changes keeps the old app version** until they are
  sent (so an update never strands them). Offline for days means the old
  version for days.
- **Initial Not saved behavior (superseded by owner decision 3).** Rejections
  used to live in memory only. They now persist in the device-local queue until
  dismissal or successful retry.
- **Browser coverage limits:** R8 and R12 remain unit-tested only. The real
  build swap with a stored change, sign-out hold, persistent Not saved entry and
  30-day warning have browser regressions.

## Owner review decision log

1. **Approved — conflict handling.** Keep the existing conservative row-level
   checks: refuse stale edits, show them under Not saved, and offer Save mine
   anyway. Matching values do not conflict; quantity deltas merge. Changes to
   different fields of the same row can still conflict. No field-by-field
   merging for this release. No implementation change needed.

2. **Approved — hold unsent changes after sign-out.** Keep them in this room's
   device-local queue, but do not send them automatically after signing back in.
   Ask the user to send or discard them. Implemented and verified by focused unit
   and browser regressions.

3. **Approved — persistent Not saved list.** Keep rejected-change entries on
   the device across reloads and app closure until dismissed or successfully
   retried. Never retry automatically. Implemented and verified by focused unit
   and browser regressions.
4. **Approved — delete wins.** Keep the existing rule: offline edits do not
   restore items or lists deleted elsewhere. Show the refusal under Not saved;
   the user can deliberately add an item again. No implementation change needed.

5. **Approved — keep the 30-day hold.** Retain the existing pause for changes
   older than 30 days, with Send or Discard. The owner sees this as a rare edge
   case and accepts keeping the built behaviour. The warning names this room's
   device-local queue and explains the duplicate-send risk.

6. **Approved — defer offline list creation.** Keep creating lists online-only
   for this release. Offline creation remains a separate Later backlog item;
   editing saved lists offline is in scope. No implementation change needed.

7. **Approved — preserve changes when access is lost.** Keep queued changes
   on the device without bypassing server authorization. Offer sign-in again
   where access can be restored, or discard where it cannot. No change to the
   existing access-loss rule; the approved post-sign-out hold still applies.

8. **Approved — delay app updates while changes wait.** Keep the current app
   version until unsent changes are resolved, rather than risk stranding them.
   Accept that an offline device can stay on an older version for days. The real
   build-swap regression is now covered by the browser suite; post-deploy device
   checks remain manual.

9. **Approved — merge duplicate item adds.** Keep one item when devices add
   the same item under the existing naming rules. Direct later queued edits to
   that item, retaining normal conflict checks. No implementation change needed.

10. **Approved — last received setting wins.** Keep last-write-wins for room
    name and hide-checked-items, including delayed offline changes. No conflict
    prompt for these easily reversible settings. No implementation change needed.

11. **Approved — preserve queue order behind held entries.** A held or unreadable
    entry blocks later queued changes for the same room on this device, not
    other people's devices. Ordinary server-rejected edit conflicts move to Not
    saved and do not block later sending, including edits to the same item.
    Keep this distinction clear in the UI. No change to the ordering rule needed.

12. **Approved — automated release checks; no pre-release manual iPhone test.**
    Run focused regressions, the full browser suite and complete automated
    checks. Include a real build swap with waiting changes if feasible. The
    owner waived pre-release iPhone testing; the waiver is not evidence that
    manual or automated tests passed. Do not push, move bookmarks or deploy as
    part of this implementation.

## Progress

- [x] 6.1 Conflict rules (this plan)
- [x] 6.2a Server conflict checks
- [x] 6.2b Deletion pruning and per-list share tracking
- [x] 6.2c Persistent queue
- [x] 6.2d Offline editing in the client
- [x] 6.3 Not-saved UI
- [x] 6.4 Multi-device tests and docs
- [x] Approved queue lifecycle improvements; complete automated checks passed, including the real build-swap browser regression
- [x] Gate C: owner waived pre-release iPhone testing; no manual test was run. Post-deploy device checks remain manual.
