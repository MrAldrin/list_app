# Handout: overnight build, 2026-10-16 to 2026-10-17

A briefing for a fresh agent. The owner wants to talk through everything one long
session did. The owner does not remember the details, so this file holds them.
Read it, then help the owner review the choices. Do not start new work unless the
owner asks.

## 1. What the owner asked for

The session started on 2026-10-16 at about 20:40. In order:

1. **Be more ambitious.** The owner asked what a strong agent could do in this
   project. Two parts:
   - Backlog items that need little or no input from the owner.
   - Offline editing as "the next big step". The owner wondered whether user
     accounts were needed first.
   - Quote: "if I gave you like a good plan and you can spin up a lot of subs and
     do this for hours and hours I think we can get far".
2. **The agent's answer:**
   - User accounts are not a blocker. Room cookies and `op_id`s already support
     offline sending. Accounts stay in Ideas.
   - It proposed 7 small items (list in section 3).
   - It proposed default conflict rules for offline editing.
   - It proposed one lead session running all subagents, not two leaders.
3. **The owner agreed:**
   - Do all small items, each in its own jj workspace.
   - Minimum password length **4**. Quote: "it's for people so no one really
     needs that". The agent pushed back: a 4-character password can be guessed
     online. It proposed a sign-in rate limit, and the owner accepted.
   - One agent leads everything.
4. **The go-ahead.** Quote, lightly trimmed:
   > "start all the sub-agents now for the seven small items … you can just move
   > integration bookmark to the finished work … to the end. Then write the rules
   > for the offline mode, but don't wait for my review … just start doing it
   > from start to finish, and then when you're finished, then we can say, Hey,
   > these are strange things I chose … We can simply throw it away if we don't
   > like it … And we don't move main before I'm back again."
5. **Next morning (2026-10-17):** the owner asked how far it got, then twice told
   it to keep going to the end ("go, go, go with the sub-agents to the very end").

**Hard rule from the owner:** `main` does not move and nothing is pushed until
the owner is back. Pushing `main` deploys to Railway. This rule was kept.

## 2. How the work was run

- One lead session. Subagents ran in separate jj workspaces under
  `/home/hsa/projects/list_app-ws/<name>`. All workspaces are now removed.
- Model policy: Haiku 5.5 at high effort first; Opus 5.5 at low effort when
  Haiku's work was not good enough.
- The lead reviewed every result, fixed small issues, rebased, and moved the
  `integration` bookmark to each accepted change (the owner allowed this).
- Browser tests: only related files during work, then the full suite once at
  the end of each step.

## 3. Result

`integration` is at `ptnxtvnn` ("plans - offline editing: 6.4 done, Gate C
next"). It holds **36 changes that are not on `main`**. `main` is still at
`uryuwkou`.

Last checks, all on the final `integration`:
- Full browser suite (Chromium, Firefox, WebKit): 312 passed, 0 failed.
- pytest: 1283 passed. Vitest: 531 passed.
- ruff format, ruff check and ty: clean.

See every change with:

```bash
jj log -r 'main..integration'
```

### 3a. The 7 small items (plus the sign-in limit)

| Item | Changes | What it does |
|---|---|---|
| Backlog follow-ups | `xvyyknzn` | Noted cleanup follow-ups (SSE, WAL, resource limits) in Later before the work started. |
| SSE refactor | `rwytrxll` | Live updates use FastAPI's `EventSourceResponse`. Our own keep-alive code is gone. The keep-alive comment is now `: ping` instead of `: keep-alive`. |
| Admin deletes a room | `lnzlvrtr`, `tlkwvtuy` | `DELETE /api/v1/admin/rooms/{slug}`, 204. A red Delete button per room in Admin. The admin must type the exact room name. Open pages of that room get `revoked`. No room password needed. |
| "N checked items hidden" | `kvkqvykm` | A muted line under the list on room and share pages. Counts only items hidden by the hide-done rule. This overrides decision 89 in `plans/svelte-frontend-rewrite.md`; a note was added there. |
| Password minimum 4 | `zyxvlmpu` | New and changed passwords must have at least 4 characters. |
| Sign-in rate limit | `ywmkqpxo` | Failed sign-ins per minute: 10 per room, 20 per client address, 10 for admin (all clients together). Then 429. Code: `src/sign_in_limiter.py`. |
| Resource limits | `nzqtsxmy`, `puqwpnow`, `wwltstkq`, `mnpktqzw` | At most 100 open live streams (503 when full). Offline snapshots not saved for 30 days are dropped. Processed ops are pruned daily while the server runs. The database opens at server start, not on import. |
| WebKit flake | `lwrkvopl` | The live-rename test now waits for the live stream before reloading. 60 of 60 runs passed. |
| Reload during DELETE | `zmlolmou` | Browser tests for a reload in the middle of sign-out and room delete. |
| Backlog cleanup | `pxznpktv` | Removed the finished items, added follow-ups. |

### 3b. Offline editing (Milestone 6, steps 6.1 to 6.4)

Before: offline pages were read-only. Unsent changes lived in memory and were
lost when the app closed.

Now: you can edit offline, the changes survive closing the app, and they are
sent when the connection is back. Changes the server refuses are listed in a
"N changes were not saved" sheet.

The plan with all rules: [`plans/offline-editing.md`](../../plans/offline-editing.md)
(`Lifecycle: tracked`). User doc: [`docs/offline-viewing.md`](../offline-viewing.md)
(now titled "Offline use"). Mechanics: [`offline-editing-details.md`](offline-editing-details.md).

| Step | Changes | What |
|---|---|---|
| 6.1 Rules | `wwkmnkms` | Conflict rules R1 to R13, written without owner review (as asked). |
| 6.2a Server checks | `wokkyllp`, `vnxronsx` | `base_seq` on set ops. New rejection `changed_meanwhile`. Answers return the row's new `changed_seq`. `item.toggle_tag` takes `active`. A duplicate add returns the existing `item_uid`. |
| 6.2b Server pruning | `ulppxrpv`, `lysxprxw` | Deletion records pruned after 90 days (migration 7). Share links get a per-list `seq` (migration 8, `share_seq_floors`), so a link holder no longer sees activity in other lists. |
| 6.2c Stored queue | `poppmqlu` | Write queue in IndexedDB (`listr-queue`), one tab sends at a time (Web Locks), format number, 30-day hold, asks for persistent storage. |
| 6.2d Editing offline | `vqvztsvz`, `qzztyolz`, `wquyxkvu`, `ppxwtmvx`, `yvwokrkq` | Edit controls work offline. The screen shows queued changes at once. The device's own later ops follow the row's new `changed_seq`. |
| API version 2 | `vppuonxn`, `kvzknpzr`, `ukrouzlq` | `API_VERSION = 2` (server and client), because the share `seq` changed meaning. Old open pages will show a Reload banner after deploy. |
| 6.3 Not-saved UI | `ltnuxmyt`, `vvqzymuw`, `twxsoluu`, `umpvxlxn` | Banner and sheet for refused changes, a mark on items with unsent changes, hints on controls that stay disabled offline. |
| 6.4 Tests and docs | `uxwtsopl`, `mpmuuxwr`, `wouswxvv`, `ptnxtvnn` | Two-device browser tests, reload keeps stored changes, docs rewritten. |

### Conflict rules in one line each

- **R1** +/− on quantity: both count.
- **R2** Tick, edit or rename of a row someone else changed meanwhile:
  **refused** (`changed_meanwhile`), unless the stored value already matches.
- **R3** The device's own queued ops on one row don't conflict with each other.
- **R4** Tag toggles carry the wanted state, so sending twice is safe.
- **R5** Edit vs delete: **delete wins**.
- **R6** Adding an item someone else added: fine; later ops go to that item.
- **R7** Renaming a list to a taken name: refused.
- **R8** Hide-done setting and room name: last write wins.
- **R9** Access lost while offline: changes kept as "can't be sent"; sign in
  again or discard.
- **R10** Changes older than 30 days: not sent automatically; the user chooses.
- **R11** Browser clears storage: changes lost; the app asks for persistent
  storage.
- **R12** Two tabs: one sends at a time.
- **R13** New app version: never deletes unsent changes.

## 4. Choices the owner should review

**Biggest change from what the owner saw on the evening:** the first proposal
said "two devices edit the same field: the last one sent wins". The written rules
(R2) chose the opposite: a stale edit is **refused**, and the user can press
"Save mine anyway". Reason: a late tick from an offline phone would otherwise
undo a newer untick. Ask the owner if they agree.

Other choices, from the "Decisions made while building" section of the plan:

- Edit conflicts compare all sent fields. A +/− on another device conflicts
  with an edit dialog that is open with the old quantity.
- Sign-out keeps stored changes on the phone. They are sent after the next
  sign-in to that room. Not cleared on a shared phone.
- Held or unreadable ops block later ops of the same room, to keep the order.
- Creating a list offline is not supported (new backlog item under Later).
- "Share list", password change, room delete, sign-in and admin stay disabled
  offline.
- The not-saved list lives in memory; a reload clears it.
- The not-saved banner count includes held ops.
- Sending is about 10 to 15 ms slower than before (IndexedDB and Web Lock
  first). A subagent proposed a complex "send first" fast path; the lead
  rejected it. Tests now wait for saved data instead.
- The sign-in limit lets an attacker lock a room's sign-in for about a minute
  by guessing wrong.
- The per-client sign-in limit trusts the first `X-Forwarded-For` entry, which
  a client can fake (backlog, Later). The per-room limit is not affected.
- Admin room delete has no request body and needs no room password.
- The `: ping` keep-alive test patches a private FastAPI name and may break on
  a FastAPI upgrade.
- `db` is typed `Any` in one place.

## 5. Known limits

- Closing the app within a few milliseconds of a tap can lose that change.
- A tab with waiting changes keeps the old app version until they are sent.
- Not covered by browser tests: a real build swap with waiting changes, and
  R8, R10, R12, R13 (unit tests only).

## 6. Problems along the way

- **Slower sends broke 3 browser tests** (6.2c). Found by bisecting. Fixed in
  the tests with `wait_until`, not with a fast path in the app.
- **Rebase conflicts:** `src/api/events.py` (stream limit vs SSE rewrite) and
  docs in 6.2d. Both resolved by hand.
- **Lead's own mistake:** after the API version bump it ran only
  `compat.test.ts`. Two tests elsewhere had "2" hardcoded as "another version"
  and broke. Fixed with `OTHER_VERSION` (current + 1).
- Agents reported a `HEAD /sw.js` test failure. It could not be reproduced; it
  needs a built frontend.
- The owner thought the session had stopped overnight. It was waiting for
  background agents; one 6.3 agent had stalled and was resumed.

## 7. What is open

1. **Gate C:** the owner tests offline editing on the iPhone, ideally with two
   devices. Listed under Manual checks in `plans/backlog.md`.
2. **Owner review** of section 4.
3. **Backlog placement** of two new Later items: "create a list offline" and
   "`X-Forwarded-For` in the sign-in limit".
4. **Deploy:** only with the owner's approval, following
   [the deployment checklist](../deployment.md#deployment-checklist). The lead
   recommended adding the staging environment first
   (`plans/staging-environment.md`), since this is the biggest change so far.
   The deploy ships migrations 7 and 8 and API version 2.

## 8. Useful commands

```bash
jj log -r 'main..integration'          # all 36 changes
jj show <change-id>                    # one change in full
jj diff --from main --to integration --stat
```

To throw work away, the owner can point `integration` back at an earlier change
(for example `jj bookmark set integration -r uryuwkou --allow-backwards`).
Do this only when the owner says so.
