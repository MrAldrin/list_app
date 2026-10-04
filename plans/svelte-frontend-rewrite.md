# Svelte frontend rewrite

Lifecycle: tracked

The step-by-step implementation plan for replacing the NiceGUI frontend with
Svelte. The direction and the reasons for it are in the
[migration plan](offline-frontend-migration.md). This file is the "how".

Status: approved by the owner on 2026-10-03 as the working plan. Reviewed on
2026-10-03 before Milestone 0; the small changes from that review are in the
[decisions log](#decisions-log) (rows 8–13).

## Read this first (for every agent session)

1. Read this whole file, then [`AGENTS.md`](../AGENTS.md) and
   [`ARCHITECTURE.md`](../ARCHITECTURE.md).
2. Find the first unchecked step in [Progress](#progress). Do that step only,
   unless the owner asks for more.
3. Work on the `svelte-frontend` branch (see [Branches](#branches)).
4. Run all [checks](#checks-for-every-step) before you call a step done.
5. Tick the step in [Progress](#progress) and add a short note if useful.
6. If you hit a decision, follow [Decisions without the owner](#decisions-without-the-owner).
7. Stop only at a [gate](#gates) or a [hard stop](#hard-stops).

The owner does **not** review between steps. Tests are the review. Make every
step leave the app working, with all checks green.

## Branches

```
main ─ … ─ tooling ─┬─ svelte-frontend   (this plan; AI implementation)
                     └─ svelte-learning   (owner's practice code; never merge)
```

- Build every step on top of the `svelte-frontend` bookmark. Move that bookmark
  to your newest change at the end of the session.
- Never build on, merge or rebase onto `svelte-learning` or
  `backup-offline-read-only`.
- One jj change per step, described as `<area> - svelte <topic>: <what>`, for
  example `api - svelte items: add item write endpoints`.
- Rebase onto `main` when `main` has moved, at the start of a session. Resolve
  conflicts carefully; `plans/backlog.md` and migrations are the likely spots.
- Nothing from this plan goes to `main` before [Gate B](#gates).
- The `field-constraints` branch also changes the schema. If it lands on `main`
  first, renumber this plan's migrations after rebasing.

## Goal and scope

Final goal: the Svelte app replaces NiceGUI and works offline on the iPhone,
including editing. We get there in milestones. Offline is **built** last, but
**designed** for from the first step, so nothing needs a second rewrite.

- **Prototype (Milestones 0–2):** the full everyday list experience in Svelte:
  room login, lists, items, tags, hide-done settings, undo and live updates.
- **Migration (Milestones 3–4):** everything else, then the switch.
- **Offline (Milestones 5–6):** viewing, then editing.
- **Not in this plan:** new features. Improvements come after the switch, in
  their own plans.

## Gates

A gate is a planned stop where the owner reviews. Between gates, agents keep
going. There are only three.

| Gate | When | Owner does |
|---|---|---|
| **A: prototype review** | After Milestone 2 | Tests on this laptop and the iPhone (local network). Reviews the [decisions log](#decisions-log). Decides: continue the migration, adjust, or stop. |
| **B: production switch** | After Milestone 4 | Approves the push to `main` (a production deploy), inside the deploy window, using the deployment checklist. |
| **C: offline review** | After Milestone 6 | Tests offline viewing and editing on the iPhone, including two devices. Accepts or asks for changes. |

## Hard stops

Stop and ask the owner, even mid-milestone, before:

- pushing or moving `main`, or touching production or Railway settings;
- deleting or rewriting user data, or a migration that cannot be rolled back;
- weakening security: authorization, password handling, tokens, cookies;
- adding a new language, framework or hosted service (small npm or Python
  libraries are fine, see [Decisions without the owner](#decisions-without-the-owner));
- deleting existing tests, or skipping a failing test to get green.

## Decisions without the owner

Most decisions should not wait for a gate.

- If there is an obvious first choice, **take it, log it, keep going.**
- Prefer choices that are cheap to undo.
- Add each one to the [decisions log](#decisions-log): what, why, the
  alternative, and the cost of changing it later.
- Only stop if the decision is a [hard stop](#hard-stops), or if both options
  are expensive to undo and no option is clearly better.

## Architecture during the migration

Both frontends run side by side on the same Python server and the same database
until the switch. NiceGUI stays the live app the whole time.

```
browser ── /            NiceGUI pages (unchanged)
        ── /app/…       built Svelte files (static)
        ── /api/v1/…    JSON API + live-update stream
                         │
                    Python (NiceGUI's FastAPI app) ── SQLite
```

- **One process.** NiceGUI's `app` is a FastAPI app. Add the API with
  `app.include_router(...)` in a new `src/api/` package. No second server.
- **Svelte is static files.** SvelteKit with `adapter-static` in SPA mode, built
  to `frontend/build/`, served by Python under `/app/` (`paths.base = '/app'`).
  At the switch it moves to `/`.
- **Local development:** run Python on 8080 and `npm run dev` on 5173. Vite
  proxies `/api` to 8080, so the browser sees one origin and cookies work.
- **Reuse the business rules.** API endpoints call `item_service.py` and
  `database_crud.py`. Do not copy rules into the API or into Svelte. The
  [item write rules](../docs/item-writes.md) apply to the API too.
- **Tooling:** Node 24 via `fnm`, npm (not bun), no global installs. Run
  `npm`/`npx` from `frontend/`. Write Svelte 5 code only (runes: `$state`,
  `$derived`, `$props`, `$effect`); no Svelte 4 patterns such as `export let`
  or `$:`.
- **Both UIs stay in sync.** API writes trigger NiceGUI's `broadcast_updates()`,
  and NiceGUI writes notify the API's live stream.

## Offline-ready design (applies from Milestone 0)

These rules exist so offline editing later is an addition, not a rewrite.

- **Stable public IDs.** Lists and items get a `uid` column: a UUID string,
  unique, never reused. The API only exposes `uid`, never the integer `id`.
  The client may create the `uid` itself, which is needed to create items
  offline. A trigger fills `uid` for rows inserted without one (NiceGUI).
  Undo of a delete creates a new row with a new `uid`.
- **Change sequence.** Each room has a `change_seq` counter. Every write in the
  room increases it and stamps the changed row with `changed_seq`. SQLite
  triggers do this, so no write path (NiceGUI, API, share, admin) can forget it.
  A room rename also bumps it, so the feed can carry the room name.
- **Deletions are recorded.** A `deletions` table stores `(room_id, kind, uid,
  changed_seq)`. Clients learn about deletions from it, so a stale device
  cannot bring a deleted item back.
- **One read path: the changes feed.**
  `GET /api/v1/rooms/{slug}/changes?since=N` returns changed lists and items,
  deletions and the new `seq`. `since=0` returns everything. Online, offline and
  after reconnect, the client always uses this feed.
- **Retry-safe writes.** Every write carries a client-made `op_id` (UUID). The
  server stores processed `op_id`s with their result for at least 30 days, and
  returns the same result if the same `op_id` arrives again. Old entries are
  pruned at startup.
- **Intent, not values.** Writes say what the user did ("toggle done", "add 1
  to quantity"), as the current NiceGUI app already does.
- **Edits carry a base version.** Rename and edit send the `changed_seq` they
  were based on. The server decides conflicts and answers with a clear result.
  Exact conflict rules are designed in Milestone 6; the fields exist from the
  start.
- **A client data layer.** All Svelte data access goes through one module
  (`frontend/src/lib/data/`): it applies the changes feed and sends write
  operations through a queue. Components never call `fetch` directly. In the
  prototype it keeps data in memory; Milestone 5 makes it store data in
  IndexedDB without changing components.

## Security rules for the API

- Room access works as today: the room password gives a room token, stored in
  an HTTP-only cookie (secure on HTTPS). The browser never stores passwords.
  On plain HTTP (local network testing) the cookie is HTTP-only but not secure;
  the Svelte app does not use the NiceGUI localStorage fallback.
- Every API request checks room access on the server, in the same transaction
  as the read or write, like the current pages do.
- Writes need a same-origin request (reuse the `Origin` check in
  `src/room_cookies.py`) and a JSON body.
- Public share links and admin get their own endpoints in Milestone 3, with the
  same limits as today: a share link never gives room access.
- Error messages must not reveal whether a room or list exists to someone
  without access.

## Checks for every step

Python changed:

```bash
uv run ruff format . && uv run ruff check --fix . && uv run pytest -q
uv run ruff format --check . && uv run ruff check .
```

Frontend changed (from `frontend/`):

```bash
npm run format && npm run lint && npm run check && npm run test && npm run build
```

From Milestone 2 on, also run the Svelte browser tests:
`uv run pytest browser_tests -q -k svelte`.

- **Python API tests** go in `tests/test_api_*.py`.
- **Frontend unit tests** use Vitest, next to the code (`*.test.ts`), mainly
  for the data layer.
- **Browser tests** use the existing Python Playwright setup in
  `browser_tests/`, in files named `test_svelte_*.py`. One Playwright stack for
  both frontends.
- Every behavior that changes data needs a test. A step is not done while a
  check is red.

## Milestones

### Milestone 0: foundations

Goal: the plumbing exists, NiceGUI is unchanged, all tests pass.

- **0.1** Frontend setup: replace `adapter-auto` with `adapter-static` (SPA
  fallback `index.html`), `paths.base = '/app'`, Vite proxy for `/api`, Vitest
  with `npm run test`. SvelteKit 3 keeps this config in `vite.config.ts`.
  Replace the starter page with a placeholder. Keep `frontend/build/` out of git.
- **0.2** Python serves `frontend/build/` at `/app/` with SPA fallback, only if
  the folder exists. Test: `/app/` returns the page, `/` still returns NiceGUI.
- **0.3** Write [`docs/api.md`](../docs/api.md): endpoint list, request and response shapes,
  error format, `op_id`, the changes feed. This is the contract for later steps.
- **0.4** Migration: `uid` on lists and items (backfill existing rows),
  `change_seq` on rooms, `changed_seq` on lists and items, `deletions` and
  `processed_ops` tables. Test the migration on a copy of a realistic database,
  and that NiceGUI still works.
- **0.5** SQLite triggers on lists, items and rooms bump `change_seq`, stamp
  `changed_seq`, fill missing `uid`s and record deletions, inside the same
  transaction as the write. Tests per existing write type.
- **0.6** Docs: add "Running the Svelte frontend" to the README and the
  dev-server setup.

### Milestone 1: the API

Goal: everything the prototype needs, as tested JSON endpoints.

- **1.1** API package `src/api/`, router under `/api/v1`, error format, the
  same-origin check for writes, and an access helper based on `room_access.py`.
- **1.2** Room session: log in with the password (sets the cookie), log out,
  "who am I". Tests: wrong password, revoked token, password change revokes.
- **1.3** Changes feed (`since`), including deletions. Tests: full load, delta,
  deletion, no access.
- **1.4** List writes: create, rename, delete. Includes the shared `op_id`
  helper (store and replay results) that all later writes use.
- **1.5** Item writes: add-or-restore, toggle done, quantity delta, edit
  details, delete, undo (restore).
- **1.6** Tags and hide-done settings writes.
- **1.7** Idempotency sweep: replaying an `op_id` returns the stored result,
  for every write type, including failed writes. Pruning of old `op_id`s.
- **1.8** Live updates: Server-Sent Events at
  `/api/v1/rooms/{slug}/events`, sending only "new seq N". The client then
  reads the changes feed. Bridge both ways with NiceGUI's `broadcast_updates`.
- **1.9** Concurrency tests: two clients, stale writes, a deleted list, a
  renamed list. Reuse the cases in `docs/item-writes.md`.

### Milestone 2: the prototype UI

Goal: the everyday list experience in Svelte, mobile-first, fast to use.
Match the current behavior and [UX decisions](../ARCHITECTURE.md#major-ux-decisions).
Copying the current layout is fine; a polished design is not needed.

- **2.1** Data layer: types, API client, changes-feed store, write queue with
  `op_id`, events subscription with reconnect. Vitest tests.
- **2.2** Room login page and the "remembered room" start page.
- **2.3** Room page: lists with create, rename and delete.
- **2.4** List page: items, add-or-restore with feedback, check off.
- **2.5** Item details: quantity +/−, edit dialog, delete with undo.
- **2.6** Tags (list tags, item tags, filter) and the hide-done settings.
- **2.7** Live updates in the UI and clear error and "unavailable list" states.
- **2.8** Browser tests: the main flows, plus two browser contexts that see
  each other's changes. Phone-sized viewport.
- **2.9** iPhone test prep: a script or README section to build and serve on
  the local network (see the [local network guide](../docs/local-network-testing.md)),
  and a short test checklist for the owner. Then stop at **Gate A**.

### Gate A checklist

Paused after Undo for a review of where Svelte differs from NiceGUI (top of
[backlog](backlog.md#next)). Resume at Tags.

For the owner, on this laptop and the iPhone. Setup and the script are in the
[local network guide](../docs/local-network-testing.md#svelte-prototype).

**Setup:** stop the normal app, run
`uv run python scripts/serve_svelte_local.py`, turn on Tailscale on the phone.
On the iPhone, open the
[HTTPS address](../docs/local-network-testing.md#https-on-the-phone) in Safari,
like production. On the laptop, open <http://localhost:8080/app/>. Room `Home`
(the script prints its code, like `home-217c10`), password
`APP_PASSWORD`.

**Separate logins:** the laptop (`localhost`) and the phone (HTTPS address) are
different sites, so each logs in on its own. On HTTPS, NiceGUI and Svelte share
the `__Host-` cookie (decisions 12 and 20); on the laptop's plain HTTP they
need separate logins.

- [x] **Login:** a wrong password says "Wrong room or password."; the right one
  opens the room. Open `/app/` again: it goes straight to the room. Log out and
  back in.
- [x] **Lists:** create, rename, delete (asks first). The same name in other
  letter case opens the existing list.
- [x] **Items:** add; add a duplicate (warning); check and uncheck; type a
  checked item's name to restore it; quantity + and − (Options); edit name,
  notes and quantity.
- [x] **Undo:** delete an item, tap Undo within 5 s. Same for a tag.
- [ ] **Tags:** add tags, tag items with the round buttons, filter by a tag.
- [ ] **Hide-done:** try All, After X days and Keep last X; a bad number shows
  a warning.
- [ ] **Live, laptop and phone:** open the same list on both. Changes on one
  show on the other within about a second, both ways.
- [ ] **NiceGUI side by side:** open the same list in NiceGUI (address without
  `/app/`). Changes show in both directions. Change the room password in
  NiceGUI: the Svelte pages ask for the password again.
- [ ] **Background and resume:** leave the phone in another app (or locked) for
  over 30 s, change something on the laptop, come back: the change is there.
- [ ] **Airplane mode:** turn it on for about 10 s, check an item ("Reconnecting…"
  or "Saving…" shows), turn it off: the change saves and the laptop shows it.
  Offline use is not built yet, so a reload while offline fails.
- [ ] **Feel on the phone:** tap sizes, the keyboard and the add field,
  scrolling, dark mode.
- [ ] **Review** the [decisions log](#decisions-log) in a fresh session. The
  agent first sorts the rows into "needs the owner" (product and UX choices),
  "worth knowing" (security and data) and "technical detail"; the owner then
  goes through only the first group, one row at a time. Then decide: continue,
  adjust or stop. Note findings (iOS version) here or tell the agent.

### Milestone 3: the rest of the app

Goal: Svelte can do everything NiceGUI does. Start after Gate A.

- **3.0** Replace the SSE shutdown workaround (reading uvicorn's internal
  `should_exit` through the signal handler in `src/api/events.py`) with
  uvicorn's official `timeout_graceful_shutdown`, passed through `ui.run()`.
  Test that stopping the server with an open stream is quick. Decided at the
  Gate A review.
- **3.1** Room management: rename room, change password, delete room. Also
  decide at the start of 3.1: say "Room not found" before the password prompt
  (changes decisions 18 and 72), and possibly a longer random part in room
  codes so that is safe. Raised at the Gate A review.
- **3.2** Public share links: view and edit by token, reset link. Port the
  [public sharing](../docs/public-sharing.md) rules and their tests.
- **3.3** Admin: login, room overview, password reset.
- **3.4** Creation invitations: issue, revoke, create a room from a link.
- **3.5** Home-screen install: manifest, icons, launch URL rules from
  [home-screen installation](../docs/home-screen-installation.md).
- **3.6** Theme, small UX details and accessibility pass. Include: creating a
  list whose name exists (any letter case) shows "Opened existing list" instead
  of opening it silently; names stay unique ignoring case. Raised at Gate A.
- **3.7** Port the remaining NiceGUI browser tests to Svelte versions. Also
  add a layout check for toasts (small, inside the screen). WebKit runs
  already, but no test checked the toast size, and only the real iPhone
  showed the full-height bug. Raised at Gate A.

### Milestone 4: the switch

Goal: Svelte serves `/`; NiceGUI is gone. Start after Milestone 3.

- **4.1** Production build: decide and document how Railway builds the frontend
  (preferred: Railway builds it; fallback: the deploy script builds it). Test
  the full build locally.
- **4.2** Move Svelte from `/app/` to `/`. Keep old URLs working
  (`/room/{slug}`, `/list/{slug}`, `/share/{token}`, `/admin`).
- **4.3** Remove NiceGUI pages, the NiceGUI dependency and the old service
  worker. Keep the API and business rules.
- **4.4** Update `ARCHITECTURE.md`, `README.md`, `docs/deployment.md` and the
  affected docs. Retire NiceGUI-only tests.
- **4.5** Rehearse the deploy with a production-like database copy. Then stop at
  **Gate B**.

### Milestone 5: offline viewing

- **5.0** HTTPS for phone testing through background Tailscale Serve. See the
  [local network guide](../docs/local-network-testing.md#https-on-the-phone).
  The script still prints direct HTTP addresses; use `tailscale serve status`
  to find the HTTPS address. Updating script output is not an offline blocker.
- **5.1** Service worker (SvelteKit's built-in support) caches the app files.
- **5.2** The data layer stores lists and items in IndexedDB, with a schema
  version for upgrades.
- **5.3** Offline and stale indicators in the UI.
- **5.4** Privacy rules: clear saved data on logout and on revoked access;
  decide what happens on shared devices.
- **5.5** Browser tests with Playwright's offline mode: cold start offline,
  reconnect, deploy update.

### Milestone 6: offline editing

- **6.1** Design note in `docs/`: conflict rules for edits, deletes, duplicate
  names and multiple devices. Pick the simplest safe rules; log them. Also
  decide how long `deletions` rows are kept and prune them; the changes feed
  then sends a full snapshot when `since` is older than the oldest kept
  record (not built yet: deletions are never pruned before this step).
- **6.2** Persist the write queue in IndexedDB; sync on reconnect and on app
  open. No reliance on iPhone background sync.
- **6.3** UI for pending, failed and conflicting changes.
- **6.4** Tests: two devices offline editing the same list, storage loss,
  revoked access while offline. Then stop at **Gate C**.

## Decisions log

Decisions taken without the owner, for review at the next gate. Newest last.

| # | Decision | Why | Alternative | Cost to change |
|---|---|---|---|---|
| 1 | API inside the NiceGUI/FastAPI process | One server, one deploy, both UIs share the DB | Separate FastAPI app | Low |
| 2 | Svelte served at `/app/` until the switch | NiceGUI stays live and untouched | Separate port or domain | Low |
| 3 | Live updates with Server-Sent Events | Simple, one-way, works over plain HTTP | WebSockets | Low |
| 4 | Integer `id` stays internal; API uses `uid` | Smallest schema change, offline-safe IDs | Replace the primary keys | Medium |
| 5 | Deletions in a separate table, not soft-delete flags | Existing queries and unique indexes stay as they are | `deleted_at` on each row | Medium |
| 6 | Browser tests in Python Playwright | One test stack for both frontends | Playwright for Node | Low |
| 7 | Prototype scope = everyday list use; management, sharing, admin in Milestone 3 | Fast route to Gate A | Everything before Gate A | Low |
| 8 | `change_seq`, `changed_seq`, `uid` fill and deletions done by SQLite triggers | One place; no write path can forget it; same transaction for free | Bump in each `database_crud.py` write | Low: drop triggers in a migration |
| 9 | The shared `op_id` helper is built with the first writes (1.4) | Later writes reuse it instead of retrofitting | Add it in 1.7 | Low |
| 10 | Undo of a delete creates a new `uid` | `uid`s are never reused, matching item IDs | Restore the old `uid` | Low |
| 11 | Room renames bump `change_seq`; the feed carries the room name | Room page header stays live | Room name only from "who am I" | Low |
| 12 | API cookie on plain HTTP is HTTP-only, not secure; no localStorage fallback | Safer than localStorage; needed for iPhone tests on the local network | Copy NiceGUI's localStorage fallback | Low |
| 13 | Old `op_id`s are pruned at startup (older than 30 days) | Simple; the table stays small | A scheduled job | Low |
| 14 | SPA fallback file is `index.html`, nothing prerendered (`ssr = false`, `prerender = false` in the root layout) | One file serves every `/app/` URL; no prerendered home page to clash with | `200.html` fallback, or prerender some pages | Low |
| 15 | Vite proxy keeps the `Host` header (no `changeOrigin`) | The server's same-origin check compares `Origin` with the host, so dev writes pass | Rewrite the host and relax the check in dev | Low |
| 16 | `/app` redirects to `/app/` with a temporary (307) redirect | The app moves to `/` at the switch; browsers must not cache the redirect | Permanent 308 | Low |
| 17 | Missing files under `/app/_app/` return 404, not `index.html`; the routes are added at startup only if `frontend/build/index.html` exists | Serving HTML as JavaScript hides errors after a deploy; no build means no `/app/` at all | Fall back for every path; check the folder on each request | Low |
| 18 | API contract: `/api/v1`, JSON only, `uid`s only, one error shape with a short fixed code list; unknown room and no access look the same | Small, predictable surface for the client and tests | Per-endpoint error shapes | Low before Milestone 2 |
| 19 | One write endpoint `POST …/ops` with intent ops; business rejections are HTTP 200 `rejected` and stored by `op_id` like successes; HTTP errors are not stored; same `op_id` with another body is 409 | One retry-safe path that the offline queue can reuse | One REST endpoint per action | Medium after Milestone 2 |
| 20 | Session endpoints set NiceGUI's `__Host-` cookies on HTTPS; on plain HTTP they use `listapp-room-<hash>` / `listapp-last-room` without `Secure` | Browsers refuse `__Host-` cookies without `Secure`, so the same name cannot work on HTTP | Drop the `__Host-` prefix everywhere (weaker) | Low |
| 21 | `item.set_done {done}` instead of `item.toggle_done` | The backend sets a value (`update_item_done`); a set is safe to replay and to queue offline, a toggle is not | A toggle op | Low |
| 22 | `list.create` with an existing name returns that list (`created: false`), not a rejection | Matches `_create_list_locked` and NiceGUI, which opens the existing list | Reject as `duplicate_name` | Low |
| 23 | Stale item ops reject with `item_not_found`; `item.delete` of a gone item is applied. Needs the item write helpers to report "no row matched" (small change in 1.5) | The client can tell the user; a repeated delete is not an error | Silent no-op as in NiceGUI | Low |
| 24 | `list.visibility` sends only changed fields; the server merges with stored values in the write transaction (extend `update_list_visibility_settings` in 1.6) | Intent, not values: two devices changing different fields do not overwrite each other | Send all three fields | Low |
| 25 | The changes feed always includes `room`; a full snapshot also when `since` is ahead of the room `seq` | Rooms have no `changed_seq`; the room object is tiny. A restored database must not leave clients with phantom data | Track room `changed_seq` | Low |
| 26 | Extra endpoint `GET /api/v1/last-room`; SSE sends a `revoked` event before closing; keep-alive every ~15 s | The last-room cookie is HTTP-only, so the start page needs the server to read it; `EventSource` cannot read an error status | Readable last-room cookie; silent close | Low |
| 27 | `base_seq` is required on `list.rename` and `item.edit` but ignored: last write wins until Milestone 6. In `recent` mode the client ranks items without `completed_at` in no fixed order | Fields exist for later conflict rules; creation order would need the integer `id` | Expose a creation rank | Low |
| 28 | Migration 3 backfills `uid`s in Python (`uuid4`); existing rows and rooms start at `changed_seq`/`change_seq` 0 | Simple and testable; a first sync (`since=0`) is a full snapshot anyway | Generate in SQL; start at 1 | Low |
| 29 | `deletions` and `processed_ops` reference `rooms` with `ON DELETE CASCADE`; `processed_ops.created_at` defaults to UTC ISO time | Foreign keys are on in the app, so a room delete leaves no orphans without extra code | Delete them in triggers or in `delete_room` | Low |
| 30 | Tests that fake a pre-versioning database now build it from the version 1 baseline (`test_invitation_migration`); `test_item_ids` runs only migrations 1–2 | Migration 2 cannot rerun on a schema with later columns and indexes; real databases never reset `user_version` | Make every migration rerunnable | Low |
| 31 | Triggers live in their own migration 4, not in migration 3 | One migration per step; the triggers can be dropped or replaced on their own | Put them in migration 3 | Low |
| 32 | Update triggers have a guard `WHEN NEW.changed_seq IS OLD.changed_seq`, on top of SQLite's default `recursive_triggers = OFF` | Without it the insert trigger's own stamp would fire the update trigger (double bump); also safe if recursive triggers are ever turned on | Column lists in `UPDATE OF` | Low |
| 33 | Every update that matches a row bumps, even with equal values (same visibility values, share-link reset) | Simple; an extra unchanged row in the feed is harmless | Compare old and new values in the trigger | Low |
| 34 | Deleting a list records a `deletions` row for each of its items, then the list | Follows from per-row triggers; clients drop the items of a deleted list anyway | Skip item rows when the list goes too | Low |
| 35 | `frontend/README.md` replaces the `sv` starter text with the dev guide; `frontend/.node-version` pins Node 24 for `fnm use` | The main README stays short and links to it; `fnm` picks the version without flags | All details in the main README; no version file | Low |
| 36 | API error handlers wrap NiceGUI's and answer only for `/api` paths; added 405, 413 and 500 `internal_error` to the error table | NiceGUI pages keep their own error pages; every API answer has the JSON shape | A catch-all `/api` route; separate app | Low |
| 37 | Room access = `database_crud.room_token_transaction()` (lock + `BEGIN`/`BEGIN IMMEDIATE` + token check, commit or roll back) wrapped by `api.access.room_access()`; HTTPS reads only `__Host-` cookies, HTTP only the plain names | Same pattern as the `*_with_room_token` functions; later steps read and write in the checked transaction | Validate first, then a second transaction | Low |
| 38 | Same-origin and JSON rules are one router-wide dependency; bodies are parsed by hand (max 64 KB), not by FastAPI body models | A route cannot forget the check; the origin check runs before any body parsing; we control the error codes | Per-route dependency; FastAPI body models | Low |
| 39 | `Cache-Control: no-store` comes from a pure ASGI middleware for `/api` paths | Covers errors too and does not buffer the SSE stream (1.8) | `BaseHTTPMiddleware`; set it per route | Low |
| 40 | Sign-in keeps an older token of the same room (no revoke); sign-out clears only the room cookie, not `last-room` | Matches NiceGUI; on HTTPS a NiceGUI tab may hold the old token | Revoke the old token on sign-in | Low |
| 41 | Sign-out with a database error is 503 and keeps the cookie | A cleared cookie with a live token would hide that sign-out failed | Clear the cookie anyway | Low |
| 42 | Sign-in password longer than 1,024 characters is 422 | Bounds bcrypt input; no room has such a password (bcrypt limit is 72 bytes) | No limit | Low |
| 43 | The feed reads stored values like NiceGUI's `get_list_data`: missing quantity 1, missing description `""`, bad or non-list tags JSON `[]` (non-text tags dropped), `completed_at` rewritten as UTC with `Z`, `null` when not done or unreadable. One `_decode_tags` helper now serves NiceGUI reads too | The client gets one clean shape; both UIs show the same values | Send raw stored values | Low |
| 44 | Deletion records are not pruned in the prototype, so the "older than the kept deletions" full snapshot never happens yet; pruning moves to 6.1 | Nothing needs it before offline use; the table is small | Prune now with a fixed age | Low |
| 45 | Feed `since` is required, 0 to 2^63−1 (else 422); lists and items come in creation order | SQLite integers are 64-bit; the client sorts anyway | Default `since=0` | Low |
| 46 | Op bodies are strict pydantic models per `type` (`extra="forbid"`, strict types); UUIDs are stored in lowercase hyphen form; the request hash is sha256 of the checked body as canonical JSON (includes `op_id` and `type`) | Typos and wrong types fail loudly (422); harmless spelling differences are not a 409 | Lax parsing; hash the raw bytes | Low |
| 47 | Each op runs in a `SAVEPOINT` inside the access transaction; a rejection rolls back to it, then the response is stored | A rejected op can never leave a partial write or a seq bump, even if a handler wrote first | Trust every handler to check before writing | Low |
| 48 | A client `uid` counts as used if any list, item or `deletions` row has it, in any room; it is checked before the name rules | `uid`s are never reused, also across rooms; a bad request stays a 422 whatever the name | Check only the same room | Low |
| 49 | `list_unavailable` message is NiceGUI's "The list is no longer available."; `item_not_found` says "The item is no longer available." (doc said "This …") | Same text in both UIs | Keep "This …" | Low |
| 50 | `list.rename` checks the list before the name; `list.delete` of a gone list is `list_unavailable` (a replay of the original delete still returns its stored `applied`) | Matches the contract ("every op with `list_uid`"); unavailable is the more useful answer | Treat a repeated delete as applied, like `item.delete` | Low |
| 51 | `src/live_updates.py` holds listeners; ops notify after commit, outside the lock, once per applied op (also `list.create` that found an existing list), never for rejections or replays. main.py's listener hands `broadcast_updates` to NiceGUI's loop with `call_soon_threadsafe` and does nothing when NiceGUI is not running; a failing listener is logged, never fails the write | API routes run in worker threads and NiceGUI refreshes create loop tasks; no circular import from main.py; 1.8 adds SSE as another listener | Call `broadcast_updates` directly; skip notify for no-change ops | Low |
| 52 | `processed_ops` pruning is a NiceGUI `on_startup` handler; a database error is logged and startup goes on. List writes reuse new locked helpers (`create_or_find_list_locked`, `rename_list_if_unique_locked`, `delete_list_locked`) that the NiceGUI paths now call too | Startup must not fail over housekeeping; one copy of each list rule | Prune in `init_database()`; separate API copies of the rules | Low |
| 53 | Item write helpers got `_locked` variants that report a stale item (`False`, or `"missing"` for the edit); the NiceGUI functions call them and ignore it, so NiceGUI keeps its silent no-op. Edit values are normalized by `item_service.normalize_item_details` / `clamp_quantity`, used by both UIs | One copy of each rule; the API can answer `item_not_found` | Separate API queries | Low |
| 54 | `quantity` and `delta` must be −1,000,000 to 1,000,000 (else 422); an edit or restore quantity below 1 saves 1, as in NiceGUI | Large numbers would overflow SQLite's 64-bit integers (a 500); the floor reuses NiceGUI's rule | 422 below 1; no bound | Low |
| 55 | `item.restore` lowercases and trims the name like `item.add`; `completed_at` must be readable (else 422) and is saved as UTC with `Z`; tags and description are saved as sent. A client `uid` is checked before the list (as in `list.create`) | The feed shape comes back unchanged; a bad time never reaches the database | Store the time as sent | Low |
| 56 | `item.delete` of an item that is gone or in another list is `applied` with no change, and still notifies listeners (decision 51: every applied op) | A repeated delete is not an error; the client cannot tell gone from moved | Reject as `item_not_found` | Low |
| 57 | `list.tag_add` trims the tag and rejects an empty one as `invalid_name` (NiceGUI ignores it silently); `list.tag_remove` and `item.toggle_tag` use the tag exactly as sent. Tags compare case-sensitively, as in NiceGUI | Same tag rules in both UIs; the client gets a clear answer for an empty tag | Lowercase or case-insensitive tags | Low |
| 58 | `list.visibility` needs at least one field (else 422). Sent fields are range-checked before the transaction (missing ones as defaults); the merged values are checked again by `update_list_visibility_settings_locked`, which the NiceGUI function now calls with all three | A no-op request is a client bug; out-of-range values never reach the database | Accept an empty change | Low |
| 59 | SSE wake-up hub in `src/live_updates.py`: one `asyncio.Event` per open stream, woken with `call_soon_threadsafe`. API writes wake their room's streams, NiceGUI writes wake all. On each wake the stream checks access and reads the seq in a worker thread, and sends `seq` only when it changed | Wakes come from worker threads and NiceGUI's loop; dedupe makes extra wakes harmless; ≤4 users need nothing fancier | A global counter with one `Condition` per loop; polling the DB | Low |
| 60 | `broadcast_updates()` = `refresh_open_pages()` + `wake_streams()`; the API listener schedules only `refresh_open_pages`, and `notify_room_changed` wakes streams itself. Three listener tests in `test_api_list_ops.py` now name `refresh_open_pages` | Each side is told once per write, and no path can loop back into the other | Let `broadcast_updates` call `notify_room_changed` with a guard flag | Low |
| 61 | Streams end on shutdown: an idle stream checks every 0.5 s whether uvicorn's `should_exit` is set, found through the installed SIGTERM handler (the bound `Server.handle_exit`) | Uvicorn waits for open responses before the app's shutdown hooks run, so an open stream blocked Ctrl+C, SIGTERM and reloads (checked by hand: >10 s hang before, ~0.6 s after, also in reload mode). NiceGUI's `Server.instance` is not set in reload workers | `timeout_graceful_shutdown` in `ui.run` (cuts every request); the `sse-starlette` package | Low |
| 62 | NiceGUI room rename, password change, admin password reset and room delete now call `wake_streams()` (they never called `broadcast_updates`). Any other change shows up at the next keep-alive, which also checks access and seq. A database error during a stream closes it without an event | Streams send the new room name or `revoked` at once; the client reconnects after a close | Leave them to the keep-alive | Low |
| 63 | Data layer split into small modules; pure logic (`feed.ts`, `overlay.ts`, `order.ts`, `visibility.ts`) outside the one runes module `room-store.svelte.ts`. Server state is immutable `Map`s in `$state.raw`, replaced on each feed | Easy to test without Svelte; the lint rule `prefer-svelte-reactivity` forbids mutable `Map`s in `.svelte.ts`; a feed is small | `SvelteMap` with in-place updates | Low |
| 64 | Overlay projects only `item.set_done` (time = click time), `item.quantity_delta`, `item.toggle_tag`, `item.delete` and the three list tag/visibility ops. An applied op leaves once the feed reached its `seq`; rejected or failed ops leave at once and set `store.notice`. No feed is applied while an op's answer is open (decision 71) | Matches the plan | Project every op | Low |
| 65 | Write queue retries (same `op_id`) on no answer, 502, 503 and 504, pausing 1, 2, 5, 10, then every 30 s; `retryNow()` skips the pause when the stream reconnects. 500 and other 4xx fail the op. After any answer whose `seq` is newer, the store refreshes | Railway and the Vite proxy answer 502/504 while Python restarts; a 500 is a bug and must not block the queue | Retry only 503 | Low |
| 66 | Actions (`room.addItem(…)` etc.) never throw: they return `{ok: true, result}` or `{ok: false, code, message}`, and resolve after the store has the op's `seq` | Pages can navigate to a new list or clear an input without a second wait | Throw on failure | Low |
| 67 | Live updates: refresh when the `seq` event differs from ours (lower means a restored database). After the browser's own reconnect: refresh and retry the queue. When the stream closes for good or sends `revoked`, ask `GET …/session`: 401 stops it and asks for sign-in, otherwise reconnect with backoff (1, 2, 5, 10, 30 s). Hidden pages are not paused; when the page becomes visible it refreshes and reopens a closed stream | Phones drop streams of hidden pages without an error | Close the stream while hidden | Low |
| 68 | `openRoom` keeps one handle per slug with a user count; `closeRoom` only stops live updates, so data and queued writes stay for the page's life. `logout` forgets the room's data and drops its queued writes | Moving between room and list pages shows data at once and never loses a write; privacy rules come in 5.4 | Dispose on close | Low |
| 69 | Client `uid`s for `list.create` and `item.add`; `newId()` falls back to `crypto.getRandomValues` without `randomUUID` (plain HTTP) | Offline-ready; the iPhone test runs over HTTP | Server-made `uid`s | Low |
| 70 | Client sorting: lists by name and items open first then name, both like SQLite `NOCASE` (folds only A–Z, then code points), ties by `uid`. Visibility port: `recent` ties go by `uid` (Python: creation id, which the API does not send); times are parsed by our own ISO parser in microseconds, a time without a zone as UTC | Same order as NiceGUI; `Date.parse` reads zone-less times as local time | `localeCompare` | Low |
| 71 | While an op's answer is open, the store applies no changes feed: a refresh waits, a feed that arrives meanwhile is dropped, and one refresh runs after the answer. The op leaves the overlay in the same step as the feed that has it. With no answer (network, 5xx) the hold is released so live updates go on during retries, and that op's projection is marked uncertain: `quantity_delta` and `toggle_tag` are not projected until its answer (other projected ops are safe to apply twice) | The server wakes streams at the same moment it answers, so the feed often came first: quantity counted twice, a toggled tag flickered on, off, on | Accept the double count during retries | Low |
| 72 | Start page sends any room code to the room page without checking that the room exists; no Admin button yet | The API never tells whether a room exists (decision 18), so a wrong code shows the password prompt and then "Wrong room or password."; admin comes in 3.3 | An endpoint that checks the slug | Low |
| 73 | Password prompt says "Enter Room Password" without the room name, and shows the API text "Wrong room or password." (NiceGUI: "Incorrect password") | Without access the API gives no room name; the same text covers a wrong code | Show the slug | Low |
| 74 | A "Log out" button in the room header (NiceGUI has none). After signing out the page opens the room again and shows the password prompt; `last-room` stays (decision 40) | The owner asked for it; reopening gives a clean store | Go to the start page | Low |
| 75 | Imports through `#lib/…` name the file with its extension (`#lib/data/index.ts`) | `package.json` subpath imports map paths literally; SvelteKit 3 allows `.ts` extensions | Relative imports | Low |
| 76 | Toasts: `lib/ui/toasts.svelte.ts` (store) and `Toast.svelte` (in the root layout). The room page turns `store.notice` (rejected or failed writes) into warning toasts; pages show success toasts themselves. The toast area is a `popover`, so it shows above an open dialog | One place for messages, like `ui.notify`; an open `<dialog>` sits in the browser's top layer, above any `z-index` | Error text inside each dialog | Low |
| 77 | Dialogs use the native `<dialog>` with `showModal()`, shown with `{#if}` (`Dialog`, `NameDialog`, `ConfirmDialog` in `lib/ui/`) | Escape, focus trap and backdrop come free; no UI library | A custom overlay `div` | Low |
| 78 | "List created" shows only when a list was created; an existing name (ignoring case) opens that list without a toast (NiceGUI says "List created" both times). Create and rename keep the dialog open on a rejection, and close it on `list_unavailable`, like NiceGUI | The toast must not claim a change that did not happen | Copy NiceGUI exactly | Low |
| 79 | Fix in the data layer: `createRoomStore()` creates each room store in its own `$effect.root`. Test `room-lifetime.svelte.test.ts` runs in happy-dom (new dev dependency); Vitest resolves Svelte with the `browser` condition | Svelte freezes a `$derived` when the effect that created it ends (`derived_inert`). Rooms are opened in the page's effect but outlive it (decision 68), so the room page showed stale lists after visiting a list | Open rooms outside any effect; jsdom | Low |
| 80 | `/app/list/[slug]` is a placeholder until 2.4; its link goes to `/app/`, which opens the last room | Room links and "create opens the list" work now | No list route yet | Low |
| 81 | List page at `/app/room/{room}/list/{list}`. `/app/list/{slug}` (the NiceGUI shape) sends the browser there with the last room (`GET /last-room`). At 4.2, `/list/{slug}` can use the same page, or the server can redirect with the list's room (NiceGUI already shows that room to anyone with the list link, via "Open room") | The changes feed is per room, so the page must know the room; with it in the URL the page never guesses, and it reuses the room's store and password prompt | A list-to-room lookup endpoint; only the last room | Low |
| 82 | A list that is missing from the loaded room shows "This list was deleted or is not in this room." with "Back to room"; without access the room password prompt shows | The client cannot tell deleted from never in this room. NiceGUI says "This list was deleted." | NiceGUI's text | Low |
| 83 | Add field: Enter or Add sends `item.add` (not optimistic, the overlay does not project adds). The field clears after added, restored and "already on the list" (as NiceGUI), and only if nothing new was typed meanwhile; other failures keep the text. Focus stays in the field. Up to 3 suggestions (names that contain the text, from all items incl. hidden), a tap adds or restores, as in NiceGUI | Fast entry on the phone; no lost typing | Clear at once before the answer | Low |
| 84 | An "Options" button (then "Done") opens "Show quantities" and "Only show minimum 2" and shows a delete button on each row, as NiceGUI's edit mode. These are page state only, reset when the page is left. The − button is disabled at 1 (NiceGUI sends a write that changes nothing) | Same layout as NiceGUI; 2.6 adds tags and hide-done settings to the same panel | Show the stepper always | Low |
| 85 | Undo of an item delete is an "Undo" button in the "Deleted X" toast, for 5 s (NiceGUI: an undo bar in Options mode, 5 s). Toasts got an optional action and duration. Delete is optimistic; the toast goes if the delete fails | The phone user sees the undo where the message is, also outside Options mode | An undo bar like NiceGUI | Low |
| 86 | The edit dialog starts from the item as it was when opened (sent as `base_seq`), closes on success, `item_not_found` and `list_unavailable`, and stays open on a blank or duplicate name (message as a toast). Saving shows no toast, as NiceGUI | Same as the list rename dialog (decision 78) | Live-update the open dialog | Low |
| 87 | Deleting a tag is optimistic and shows "Deleted tag X" with "Undo" for 5 s (undo = `list.tag_add`, then "Restored tag X"), like item deletes (decision 85). The "Add Tag" field ignores a blank or existing tag (exact match) and keeps the text, as NiceGUI; it clears after a success unless retyped | One undo pattern on the phone | NiceGUI's undo bar | Low |
| 88 | The tag filter is page state. A filter on a tag that is gone (deleted here or elsewhere) stops filtering; NiceGUI keeps filtering by a tag it no longer shows. Hiding runs on the whole list before the filter | No empty list with no visible reason | Copy NiceGUI | Low |
| 89 | Hide mode is a radio group styled as a segmented control; a number saves on `change` (blur or Enter) and only when it differs; a bad number shows NiceGUI's warning and resets the field. No hidden-items count or "show hidden" button (NiceGUI has none) | Accessible single choice; no write per keystroke | NiceGUI's write on every blur | Low |
| 90 | Tag colors keep NiceGUI's order (blue, green, red, orange, purple, teal, pink) as Material 700 shades, 300 in dark mode; item tag buttons are 32 px circles | Quasar's 500 shades are hard to read as outlined text on white; rows stay one line on a phone | Quasar's colors; 44 px buttons | Low |
| 91 | Connection indicator: the store reports `live` (stream state), `queued` and `retrying`; pure `connectionStatus()` turns them into "Reconnecting…", "Connecting…" or "Saving…", shown as a small pill at the top only after 800 ms. Failed and rejected writes stay warning toasts with the server's message (decision 76) | Quick saves never flicker; short texts fit between the header buttons on a phone | A banner; a count of waiting changes | Low |
| 92 | The stream is reopened when a page was hidden for 30 s or more. A `seq` event also reads the feed when the last read failed (`store.stale`), so a failed first load heals when the stream gets through | Keep-alives are comments, which `EventSource` does not report, so a dead connection on a phone cannot be seen; without the stale check an equal `seq` never retried | A client watchdog with server `ping` events | Low |
| 93 | First-load failure shows "Could not load this room." (or list) with the error text and Retry (NiceGUI: "Could not verify room access. Please retry."). The start page and `/app/list/{slug}` get Retry for a failed last-room check. A root `+error.svelte` shows "Page not found" with a link to the start page | Says what failed and why; one `LoadError` component | Copy NiceGUI's text | Low |
| 94 | Svelte browser tests run in Chromium, Firefox and WebKit (the shared `browser` fixture) on a 390×844 touch screen, without `is_mobile` | Same engines as the NiceGUI tests; `is_mobile` works only in Chromium; Playwright's WebKit is still not iPhone Safari (Gate A found a toast bug only the iPhone showed) | Chromium only | Low |
| 95 | A session fixture runs `npm run build` when `frontend/build/index.html` is missing or older than any frontend source; without `npm` the tests fail with "run `npm run build`". A file lock stops parallel workers from building twice | A stale build would test old code; never a silent skip | Always fail and ask for a build | Low |
| 96 | `conftest.py`: the `sessions` cleanup (screenshots, traces, browser errors) moved into a `BrowserSessions` class, shared with a new `open_session(role, **options)` factory. NiceGUI steps in Svelte tests use their own desktop context and login | One copy of the diagnostics; NiceGUI and Svelte keep separate logins on HTTP anyway | Copy the fixture | Low |
| 97 | Phone test script `scripts/serve_svelte_local.py`: builds, then runs `src/main.py` with a test database in `~/.local/share/list_app/svelte-phone-test/` (own NiceGUI storage, no auto-reload), port 8080, and prints the `/app/` address per network (Tailscale first). It refuses the repository's `list.db` | Port 8080 is the one the firewall and Tailscale rules allow; the folder sits next to the deploy backups, outside the repo; the normal start is unchanged | A README section only; a shell script | Low |

## Progress

Milestone 0: foundations
- [x] 0.1 Frontend setup (adapter-static, base `/app`, `/api` proxy, Vitest 5 with `npm run test`)
- [x] 0.2 Python serves `/app/` (`src/svelte_frontend.py`; restart the server after the first build)
- [x] 0.3 API contract doc ([`docs/api.md`](../docs/api.md); decisions 18–27)
- [x] 0.4 Offline-ready schema migration (migration 3; tested on a copy of `list.db`: 4 rooms, 4 lists, 46 items kept, 50 unique `uid`s; decisions 28–30)
- [x] 0.5 Writes bump `change_seq` and record deletions (migration 4; [change tracking](../docs/change-tracking.md); decisions 31–34. NiceGUI needs no code change: the triggers cover its writes and it never selects `*`)
- [x] 0.6 README dev setup (README section + [frontend guide](../frontend/README.md); decision 35)

Milestone 1: API
- [x] 1.1 API package and access helper (`src/api/`, [`tests/test_api_basics.py`](../tests/test_api_basics.py); decisions 36–39)
- [x] 1.2 Room session (`src/api/session.py`, [`tests/test_api_session.py`](../tests/test_api_session.py); decisions 40–42)
- [x] 1.3 Changes feed (`src/api/changes.py`, [`tests/test_api_changes.py`](../tests/test_api_changes.py); decisions 43–45)
- [x] 1.4 List writes (`src/api/ops.py`, `src/api/idempotency.py`, `src/live_updates.py`, [`tests/test_api_list_ops.py`](../tests/test_api_list_ops.py); decisions 46–52)
- [x] 1.5 Item writes (`src/api/ops.py`, [`tests/test_api_item_ops.py`](../tests/test_api_item_ops.py), shared `tests/api_helpers.py`; decisions 53–56)
- [x] 1.6 Tags and hide-done writes (`src/api/ops.py`, [`tests/test_api_tag_ops.py`](../tests/test_api_tag_ops.py); decisions 57–58)
- [x] 1.7 Idempotent `op_id` ([`tests/test_api_idempotency.py`](../tests/test_api_idempotency.py): applied and rejected case per op type; no code change needed; `docs/api.md` checked against every op)
- [x] 1.8 Live updates (SSE + NiceGUI bridge) (`src/api/events.py`, `src/live_updates.py`, [`tests/test_api_events.py`](../tests/test_api_events.py); decisions 59–62)
- [x] 1.9 Concurrency tests ([`tests/test_api_concurrency.py`](../tests/test_api_concurrency.py): two clients, stale item and list writes, renames (the `uid` and the slug stay), add race, quantity sums, undo after re-add, NiceGUI writes interleaved, parallel threads; no bug found, no code change)

Milestone 2: prototype UI
- [x] 2.1 Data layer (`frontend/src/lib/data/`, entry point `index.ts`: `openRoom(slug)` returns `store` + actions; Vitest next to each module; decisions 63–70)
  - Fix after review: feeds are held while a write's answer is open, so a write never shows twice or flickers (decision 71; race tests in `room-store.test.ts` and `index.test.ts`).
- [x] 2.2 Room login and start page (`frontend/src/routes/+page.svelte`, `routes/room/[slug]/`, `lib/room/`, `lib/room-link.ts`, global `src/app.css`; decisions 72–75)
- [x] 2.3 Room page (`frontend/src/lib/room/RoomLists.svelte`, toasts and dialogs in `lib/ui/`, list page placeholder; fix: room stores outlive the page that opened them, `room-lifetime.svelte.test.ts`; decisions 76–80)
- [x] 2.4 List page: items, add, check (`frontend/src/routes/room/[slug]/list/[list]/`, `lib/list/`, old link shape `routes/list/[slug]`; notice toasts shared in `lib/ui/notice-toasts.svelte.ts`; decisions 81–83)
- [x] 2.5 Quantity, edit, delete with undo (`lib/list/ItemRow.svelte`, `ItemDialog.svelte`, `ListOptions.svelte`; toast actions in `lib/ui/toasts.svelte.ts`; decisions 84–86)
- [x] 2.6 Tags and hide-done settings (`lib/list/ListTags.svelte`, `HideDoneSettings.svelte`, `tags.ts`, `hide-done.ts`, tag buttons in `ItemRow.svelte`, colors in `app.css`; decisions 87–90)
- [x] 2.7 Live updates and error states (`lib/ui/ConnectionStatus.svelte`, `LoadError.svelte`, `routes/+error.svelte`, `lib/data/status.ts`, stream state in `events.ts` and the store; checked by hand with two browsers, NiceGUI, a server restart, a revoked password and faked 503s; decisions 91–93)
- [x] 2.8 Browser tests (`browser_tests/test_svelte_{rooms,items,live}.py`, helpers `svelte_app.py`, fixtures `svelte_build`, `svelte_server`, `open_session` in `conftest.py`; 8 tests × 2 engines, about 15 s with the default workers; stable over repeated runs; decisions 94–96)
- [x] 2.9 iPhone test prep (`scripts/serve_svelte_local.py`, test `tests/test_serve_svelte_local.py`, [local network guide](../docs/local-network-testing.md#svelte-prototype), [Gate A checklist](#gate-a-checklist), backlog Manual checks entry; decision 97)
- [ ] **Gate A: owner prototype review**

Milestone 3: rest of the app
- [ ] 3.0 Official shutdown timeout for SSE
- [ ] 3.1 Room management (incl. "Room not found" and room code length)
- [ ] 3.2 Public share links
- [ ] 3.3 Admin
- [ ] 3.4 Creation invitations
- [ ] 3.5 Home-screen install
- [ ] 3.6 Theme, UX and accessibility
- [ ] 3.7 Port remaining browser tests (incl. toast layout check)

Milestone 4: switch
- [ ] 4.1 Production build
- [ ] 4.2 Svelte at `/`, old URLs kept
- [ ] 4.3 Remove NiceGUI
- [ ] 4.4 Docs update
- [ ] 4.5 Deploy rehearsal
- [ ] **Gate B: owner approves production switch**

Milestone 5: offline viewing
- [x] 5.0 HTTPS for phone testing: owner enabled background Tailscale Serve
  without Funnel, opened the Svelte room on iPhone over HTTPS, and confirmed
  sign-in survived a refresh. HTTP port 8080 access remains allowed by choice.
  Script output is unchanged; the guide explains how to find the HTTPS URL.
  This verifies phone access and refresh persistence, not offline support.
- [ ] 5.1 Service worker
- [ ] 5.2 IndexedDB storage
- [ ] 5.3 Offline indicators
- [ ] 5.4 Privacy rules
- [ ] 5.5 Offline browser tests

Milestone 6: offline editing
- [ ] 6.1 Conflict rules design
- [ ] 6.2 Persistent write queue and sync
- [ ] 6.3 Pending/failed/conflict UI
- [ ] 6.4 Multi-device offline tests
- [ ] **Gate C: owner offline review**
