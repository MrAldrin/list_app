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

Resume at Review, in a fresh session. The NiceGUI difference review is done (decision 98).

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
- [x] **Tags:** add tags, tag items with the round buttons, filter by a tag.
  An exact duplicate warns; another letter case is a new tag.
- [x] **Hide-done:** try All, After X days and Keep last X; a bad number shows
  a warning.
- [x] **Live, laptop and phone:** open the same list on both. Changes on one
  show on the other within about a second, both ways.
- [x] **NiceGUI side by side:** open the same list in NiceGUI (address without
  `/app/`). Changes show in both directions. Change the room password in
  NiceGUI: the Svelte pages ask for the password again.
  Finding: after a Svelte rename, the open NiceGUI list page keeps the old
  title until reload (the room page updates). Not fixed: NiceGUI goes in 4.3.
- [x] **Background and resume:** leave the phone in another app (or locked) for
  over 30 s, change something on the laptop, come back: the change is there.
- [x] **Airplane mode:** turn it on for about 10 s, check an item ("Reconnecting…"
  or "Saving…" shows), turn it off: the change saves and the laptop shows it.
  Offline use is not built yet, so a reload while offline fails.
  Fixed: the status pill was hidden behind the sticky top bar.
- [x] **Feel on the phone:** tap sizes, the keyboard and the add field,
  scrolling, dark mode.
  Finding: after a dark mode switch, Safari's bars keep the old color until
  you scroll. A `theme-color` tag came in 3.6 (decision 138); the iPhone
  check is in the backlog.
  Also fixed: dialogs close on a click outside; the edit dialog no longer
  opens the keyboard; suggestions hide when the add field loses focus.
- [x] **Review** the [decisions log](#decisions-log) in a fresh session. The
  agent first sorts the rows into "needs the owner" (product and UX choices),
  "worth knowing" (security and data) and "technical detail"; the owner then
  goes through only the first group, one row at a time. Then decide: continue,
  adjust or stop. Note findings (iOS version) here or tell the agent.
  Outcome (2026-10-05): **continue**. The owner went through rows 7, 22/78,
  57, 72/73, 83–89, 91 and 93 and kept them all. Changes, in the
  [backlog](backlog.md): Next, before Milestone 3: save "Show quantities" and
  "Only show minimum 2" per list (84; later decided differently, see the row), and an "Opened existing list" info
  toast (78). Later: longer undo (85, 87). Ideas: a hidden-items count (89).
  Manual checks: time the reconnect after going offline (67, 92). The
  testing fixes above get no decision rows; they match NiceGUI.

### Milestone 3: the rest of the app

Goal: Svelte can do everything NiceGUI does. Start after Gate A.

- **3.0** Replace the SSE shutdown workaround (reading uvicorn's internal
  `should_exit` through the signal handler in `src/api/events.py`) with
  uvicorn's official `timeout_graceful_shutdown`, passed through `ui.run()`.
  Test that stopping the server with an open stream is quick. Decided at the
  Gate A review.
- **3.1** Room management: rename room, change password, delete room. The
  owner decided at Gate A (rows 72/73) to keep "Wrong room or password" for an
  unknown room; so no "Room not found" and no longer room codes.
- **3.2** Public share links: view and edit by token, reset link. Port the
  [public sharing](../docs/public-sharing.md) rules and their tests.
- **3.3** Admin: login, room overview, password reset.
- **3.4** Creation invitations: issue, revoke, create a room from a link.
- **3.5** Home-screen install: manifest, icons, launch URL rules from
  [home-screen installation](../docs/home-screen-installation.md).
- **3.6** Theme, small UX details and accessibility pass. Include: names stay
  unique ignoring case. Raised at Gate A.
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
- **4.0** Owner decisions after Milestone 3 (decisions 144–146), before 4.3:
  - Admin sign-in with its own cookie, like the room cookie: `__Host-`,
    `Secure` on HTTPS, HTTP-only. A changed `APP_PASSWORD` ends all admin
    sessions. No rate limiting (decision 144).
  - Toasts work while a dialog is open: tapping a toast's × must not close the
    dialog (decision 145).
  - The share page shows "back to room" and "Reset share link" when this
    browser has access to the list's room, as NiceGUI. Without room access
    the page reveals nothing about the room (decision 146).
  - Owner phone test fixes (decision 149):
    - "Log out" moves into the room's ⋮ menu, as the last item.
    - "Back to admin" shows on the room page whenever this browser is signed
      in as admin, not only with `?admin=true` (it got lost after opening a
      list and going back).
    - The admin key button gets the text "Reset password". The dialog title
      says it is an admin reset of the room password and explains what
      happens (check what really happens to signed-in members first).
    - List page top bar: the list name sits in the bar between the back arrow
      and the menus, cut off with "…" when long. Dark mode moves into the ⋮
      menu. The list options button stays outside, close to ⋮.
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

- Per-list change tracking for share links is decided and gets built in
  Milestone 5 or 6; 6.1 only designs how (decision 147).

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
| 78 | "List created" shows only when a list was created; an existing name (ignoring case) opens that list with an info toast "Opened existing list" (NiceGUI says "List created" both times). Create and rename keep the dialog open on a rejection, and close it on `list_unavailable`, like NiceGUI | The toast must not claim a change that did not happen; the owner asked at Gate A to be told the list already existed | Copy NiceGUI exactly | Low |
| 79 | Fix in the data layer: `createRoomStore()` creates each room store in its own `$effect.root`. Test `room-lifetime.svelte.test.ts` runs in happy-dom (new dev dependency); Vitest resolves Svelte with the `browser` condition | Svelte freezes a `$derived` when the effect that created it ends (`derived_inert`). Rooms are opened in the page's effect but outlive it (decision 68), so the room page showed stale lists after visiting a list | Open rooms outside any effect; jsdom | Low |
| 80 | `/app/list/[slug]` is a placeholder until 2.4; its link goes to `/app/`, which opens the last room | Room links and "create opens the list" work now | No list route yet | Low |
| 81 | List page at `/app/room/{room}/list/{list}`. `/app/list/{slug}` (the NiceGUI shape) sends the browser there with the last room (`GET /last-room`). At 4.2, `/list/{slug}` can use the same page, or the server can redirect with the list's room (NiceGUI already shows that room to anyone with the list link, via "Open room") | The changes feed is per room, so the page must know the room; with it in the URL the page never guesses, and it reuses the room's store and password prompt | A list-to-room lookup endpoint; only the last room | Low |
| 82 | A list that is missing from the loaded room shows "List not found. It may have been deleted.", or "This list was deleted." when it vanished while the page showed it, with a centered "Back to room" button; without access the room password prompt shows | The client cannot tell deleted from never in this room on load, but knows it when the list goes while open (as NiceGUI). Changed at the difference review | "This list was deleted or is not in this room." | Low |
| 83 | Add field: Enter or Add sends `item.add` (not optimistic, the overlay does not project adds). The field clears after added, restored and "already on the list" (as NiceGUI), and only if nothing new was typed meanwhile; other failures keep the text. Focus stays in the field. Up to 3 suggestions (names that contain the text, from all items incl. hidden), a tap adds or restores, as in NiceGUI | Fast entry on the phone; no lost typing | Clear at once before the answer | Low |
| 84 | An "Options" button (then "Done") opens "Show quantities" and shows a delete button on each row, as NiceGUI's edit mode. A quantity of 2 or more always shows as "×2" after the name; "Show quantities" adds the − / + stepper on every row instead. "Show quantities" is personal, saved per list in the browser (`localStorage`); "Only show minimum 2" is dropped. NiceGUI keeps its old switches until the switch. The − button is disabled at 1 (NiceGUI sends a write that changes nothing) | Owner at Gate A: a quantity is data everyone must see; the stepper is a personal editing tool; no accounts, so per device | Save both switches per list for everyone; show the stepper always | Low |
| 85 | Undo of an item delete is an "Undo" button in the "Deleted X" toast, for 5 s (NiceGUI: an undo bar in Options mode, 5 s). Toasts got an optional action and duration. Delete is optimistic; the toast goes if the delete fails | The phone user sees the undo where the message is, also outside Options mode | An undo bar like NiceGUI | Low |
| 86 | The edit dialog starts from the item as it was when opened (sent as `base_seq`), closes on success, `item_not_found` and `list_unavailable`, and stays open on a blank or duplicate name (message as a toast). Saving shows no toast, as NiceGUI | Same as the list rename dialog (decision 78) | Live-update the open dialog | Low |
| 87 | Deleting a tag is optimistic and shows "Deleted tag X" with "Undo" for 5 s (undo = `list.tag_add`, then "Restored tag X"), like item deletes (decision 85). The "Add Tag" field ignores a blank or existing tag (exact match) and keeps the text, as NiceGUI; it clears after a success unless retyped | One undo pattern on the phone | NiceGUI's undo bar | Low |
| 88 | The tag filter is page state. A filter on a tag that is gone (deleted here or elsewhere) stops filtering; NiceGUI keeps filtering by a tag it no longer shows. Hiding runs on the whole list before the filter | No empty list with no visible reason | Copy NiceGUI | Low |
| 89 | Hide mode is a radio group styled as a segmented control; a number saves on `change` (blur or Enter) and only when it differs; a bad number shows NiceGUI's warning and resets the field. No hidden-items count or "show hidden" button (NiceGUI has none) | Accessible single choice; no write per keystroke | NiceGUI's write on every blur | Low |
| 90 | Tag colors keep NiceGUI's order (blue, green, red, orange, purple, teal, pink) as Material 700 shades, 300 in dark mode; item tag buttons are 26 px circles (32 px until the difference review, decision 98) | Quasar's 500 shades are hard to read as outlined text on white; rows stay one line on a phone | Quasar's colors; 44 px buttons | Low |
| 91 | Connection indicator: the store reports `live` (stream state), `queued` and `retrying`; pure `connectionStatus()` turns them into "Reconnecting…", "Connecting…" or "Saving…", shown as a small pill at the top only after 800 ms. Failed and rejected writes stay warning toasts with the server's message (decision 76) | Quick saves never flicker; short texts fit between the header buttons on a phone | A banner; a count of waiting changes | Low |
| 92 | The stream is reopened when a page was hidden for 30 s or more. A `seq` event also reads the feed when the last read failed (`store.stale`), so a failed first load heals when the stream gets through | Keep-alives are comments, which `EventSource` does not report, so a dead connection on a phone cannot be seen; without the stale check an equal `seq` never retried | A client watchdog with server `ping` events | Low |
| 93 | First-load failure shows "Could not load this room." (or list) with the error text and Retry (NiceGUI: "Could not verify room access. Please retry."). The start page and `/app/list/{slug}` get Retry for a failed last-room check. A root `+error.svelte` shows "Page not found" with a link to the start page | Says what failed and why; one `LoadError` component | Copy NiceGUI's text | Low |
| 94 | Svelte browser tests run in Chromium, Firefox and WebKit (the shared `browser` fixture) on a 390×844 touch screen, without `is_mobile` | Same engines as the NiceGUI tests; `is_mobile` works only in Chromium; Playwright's WebKit is still not iPhone Safari (Gate A found a toast bug only the iPhone showed) | Chromium only | Low |
| 95 | A session fixture runs `npm run build` when `frontend/build/index.html` is missing or older than any frontend source; without `npm` the tests fail with "run `npm run build`". A file lock stops parallel workers from building twice | A stale build would test old code; never a silent skip | Always fail and ask for a build | Low |
| 96 | `conftest.py`: the `sessions` cleanup (screenshots, traces, browser errors) moved into a `BrowserSessions` class, shared with a new `open_session(role, **options)` factory. NiceGUI steps in Svelte tests use their own desktop context and login | One copy of the diagnostics; NiceGUI and Svelte keep separate logins on HTTP anyway | Copy the fixture | Low |
| 97 | Phone test script `scripts/serve_svelte_local.py`: builds, then runs `src/main.py` with a test database in `~/.local/share/list_app/svelte-phone-test/` (own NiceGUI storage, no auto-reload), port 8080, and prints the `/app/` address per network (Tailscale first). It refuses the repository's `list.db` | Port 8080 is the one the firewall and Tailscale rules allow; the folder sits next to the deploy backups, outside the repo; the normal start is unchanged | A README section only; a shell script | Low |
| 98 | Gate A difference review against NiceGUI. Match NiceGUI: on the list page the top bar (back, Options) and the add field stay on screen (`position: sticky`); long list and item names stay on one line with "…"; Options on/off settings are sliding switches; the row quantity stepper is a compact grey box (20 px buttons, same-width digits). Item rows are 36 px high (checkbox tap area stays 44 px wide). Keep Svelte: start page errors under the field, start card near the top, toasts at the bottom, the browser checkbox, hint text instead of floating labels | The owner decided each row; phone rows need room for tags, stepper and delete; the keyboard covers centered content | Full NiceGUI look; 44 px rows | Low |
| 99 | Streams end on shutdown through uvicorn's `timeout_graceful_shutdown`, set to 1 s (`SHUTDOWN_TIMEOUT_SECONDS` in `src/main.py`, passed through `ui.run()`; the browser test server passes it too). Replaces decision 61: the `should_exit` check and the 0.5 s poll in `src/api/events.py` are gone. Uvicorn logs "Cancel N running task(s), timeout graceful shutdown exceeded" when it cuts a stream; that is expected. The two tests of the old check were replaced by `tests/test_server_shutdown.py`, which starts `src/main.py`, opens a stream and sends SIGTERM (fails without the timeout; about 1.3 s with it). Ctrl+C in reload mode checked by hand: 1.3 s | Owner decision at Gate A: official setting over uvicorn internals. 1 s is far longer than any normal request (SQLite writes take milliseconds) and keeps reloads quick | 2–5 s (slower reloads and deploy stops while a stream is open) | Low |
| 100 | `room.rename {name}` is an op: retry-safe like the others, no `base_seq` (rooms have no `changed_seq`). Trimmed, case kept, names need not be unique; blank is `invalid_name` "Name cannot be empty" (NiceGUI's dialog text). Applied renames notify like every op, so open NiceGUI room pages refresh too (NiceGUI's own rename only wakes streams) | Same rules as NiceGUI through `rename_room_locked`; one write path for the queue | A separate endpoint | Low |
| 101 | Change password (`POST …/password`) and delete room (`DELETE /api/v1/rooms/{slug}` with a JSON body) are their own endpoints, not ops: no `op_id`, nothing stored, not queued, not retry-safe. A lost answer of a password change means the new cookie never arrived: sign in with the new password | An op stores a sha256 of its body for 30 days; with a password inside, that is a fast-hash copy of the password. Both need the server at once anyway | Ops with the password left out of the hash | Low |
| 102 | Both check room access (the cookie) first, then the password, in one write transaction (`change_room_password_locked`, `delete_room_with_password_locked`; NiceGUI's functions now share them). No access is 401 `not_authenticated`, identical for an unknown room. A wrong password is a new code, 403 `wrong_password`, with NiceGUI's texts "Incorrect current password" and "Incorrect password" | NiceGUI's rules as they are (access, then password); the client treats 401 as "signed out", which a typo is not | 401 `invalid_password` | Low |
| 103 | New password: blank (only spaces) is refused, as NiceGUI's dialog, and saved as typed. Longer than 72 bytes is 422 with a message (`check_new_room_password`); NiceGUI fails there with "Could not change the password" because bcrypt 5 raises. Passwords in bodies at most 1,024 characters, as sign-in | Same rules; a clear answer instead of a 500. No rule is weaker than NiceGUI's | Trim the password; let bcrypt fail | Low |
| 104 | Password change sets new room and `last-room` cookies, like sign-in. Streams are woken after the answer is sent (a background task), and the client's "who am I" check waits while its own password change is open | Our own stream is revoked too; a "who am I" with the old token gets 401 and clears the cookie, which could remove the new one | Keep the old token for this device | Low |
| 105 | Delete room clears the room cookie, and `last-room` only when it names this room, then wakes the room's streams (as NiceGUI; open NiceGUI pages are not refreshed). The client forgets the room (status `loading`, so no password prompt flashes), shows "Room deleted" and goes to the start page. Deletion records and stored ops go by cascade (decision 29) | Matches NiceGUI's `/`; a later sign-in says "Wrong room or password." (Gate A, rows 72/73) | Keep `last-room` | Low |
| 106 | A "Room menu" (⋮) button next to "Log out" opens a native `popover` with three plain buttons, placed under the button by script: "Rename Room", "Change Password", "Delete Room" (NiceGUI's texts). Share link and install help join it in 3.2 and 3.5. The rename dialog ("Rename Room", "New name") shows no toast on success, as NiceGUI; password and delete errors are toasts and the dialog stays open | Escape and outside clicks close it for free; no menu library; an ARIA `menu` would need arrow-key handling | A dialog with the actions; an ARIA menu | Low |
| 107 | Share-holder API: `GET /api/v1/share/{token}/changes`, `POST …/ops`, `GET …/events`, token in the path (like NiceGUI's `/share/{token}`). A token that opens no list (never issued, reset, list deleted) is 401 `share_unavailable`, all identical. The token is checked in the same transaction as each read and write (`share_token_transaction`, beside `room_token_transaction`) | A 401 pauses the client's write queue, so a queued edit or undo is never applied after a reset (NiceGUI's rule); the store, queue and stream are reused unchanged | 404; a share cookie | Low |
| 108 | The share feed is always a full snapshot of the one list, with `room: null`, `deletions: []` and the list `slug` as `""`; `since` is checked but not used. Its `seq` is the room's `seq`, like op answers and the stream. **Worth knowing:** a link holder can see the room's counter rise when other lists change (how often and when, no content); NiceGUI's public page also gets a refresh for every write | Deletion records have no list column, so a delta would name items of other lists; the slug is room navigation; one list is small. The room `seq` keeps the store's rules (overlay, catch-up) as they are | A per-list counter (needs a migration and trigger change) | Low |
| 109 | Share ops: `list.tag_add`, `list.tag_remove`, `list.visibility` and every item op, as on NiceGUI's public page; other types are 422. Handlers take an `OpScope` (room, plus the shared list) instead of a room id, so a `list_uid` other than the shared list's is `list_unavailable`. Share ops are stored per room in `processed_ops` like room ops | One copy of each rule; no list rename, delete or room change by link | Separate share handlers | Low |
| 110 | Room members read and reset the link with `GET`/`POST /api/v1/rooms/{slug}/lists/{list_uid}/share-link` (`{}` body), not an op. Reset checks room access and the list's room in one write transaction, then notifies (NiceGUI pages refresh, streams wake: share streams send `revoked`). Another room's or a gone list is 404 `list_unavailable`. NiceGUI's `rotate_list_share_token` now uses the same `rotate_share_token_locked` | The answer holds a token, which must not be stored for replays; a second reset does no harm | A `list.reset_share` op | Low |
| 111 | Client: `openShare(token)` gives a `RoomHandle` whose API is a `ShareApi` adapter (token in place of the slug). Its "who am I" reads the share feed; "Share List" returns its own token without a request; room-only calls fail without a request | Pages, store, queue and live updates work the same for both | A separate share store | Low |
| 112 | Placement as NiceGUI: the list header gets a ⋮ "List menu" with "Share List" and, for room members, "Reset share link"; the room menu gets "Share Room" first (decision 106 expected the share link there, but NiceGUI shares the list from the list menu and the room link from the room menu). The popover code moved to `lib/ui/MenuButton.svelte`; the list page body moved to `lib/list/ListView.svelte`, used by the list page and the share page | Same places as NiceGUI; one copy of the list UI | Share in the room menu | Low |
| 113 | The share page never shows a back link or "Reset share link", also when this browser has room access (NiceGUI then shows both) | The share endpoints never read room cookies, so a link page stays public; members reset from the room's list page | Check the room cookie on the share page | Low |
| 114 | "Share List" opens the share sheet (`navigator.share`) and falls back to a "Share this list" dialog with "Copy link" (clipboard API, else the selected text with `execCommand('copy')` on plain HTTP). The token is read when the menu opens, so the sheet opens straight from the tap. Links are `/app/share/{token}` until 4.2. A reset shows "Share link reset" (NiceGUI reloads without a toast); a failed reset shows the server's message and keeps the dialog only when busy or offline | Browsers allow the share sheet only right after a tap; the toast tells the member it worked | `/share/{token}` (opens NiceGUI) | Low |
| 115 | `app.html` sets `<meta name="referrer" content="same-origin">` for every Svelte page (NiceGUI: `no-referrer` on list pages) | `no-referrer` makes browsers send `Origin: null` on same-origin `POST`s, which the API's same-origin check refuses; other sites still get no referrer, so link addresses do not leak | `referrerPolicy` per request plus `no-referrer` | Low |
| 116 | Share page texts as NiceGUI: a link that opens nothing on load says "This list was deleted or you no longer have access."; one that stops while open says "This list was deleted or this share link was reset.", and the list goes away. A write sent after a reset gets 401 and waits unsent in the queue | Same texts in both UIs; nothing is written with the old link | Retry or drop the write with a toast | Low |
| 117 | Admin API sign-in reuses NiceGUI's admin session: the `authenticated` flag in `app.storage.user`, found through NiceGUI's signed `session` cookie (`src/admin_access.py` names the key). No new token or cookie. **Worth knowing:** as in NiceGUI, that cookie has Starlette's defaults (14 days, `HttpOnly`, `SameSite=Lax`, no `Secure` flag), and a changed `APP_PASSWORD` does not end admin sessions; both are unchanged | Same strength as NiceGUI by construction; a new admin token or cookie is a security design (hard stop) the owner has not asked for. Signing in or out on one UI does the same on the other, like room cookies (decision 20) | An own `__Host-` admin token cookie (stronger, needs the owner) | Low |
| 118 | Admin endpoints under `/api/v1/admin`: `session` (POST/GET/DELETE), `GET`/`POST rooms`, `POST rooms/{slug}/password`. The admin check is a router dependency, after the same-origin check and before the body or room is read (401 `admin_required`, "Admin sign-in required"). A wrong password is 401 `invalid_password` "Wrong password" (NiceGUI's text) and keeps an admin session signed in. The password check is shared with NiceGUI (`admin_password_matches`, constant time; NiceGUI used `==`). No rate limiting, as NiceGUI. Endpoints are `async` (NiceGUI's storage must change on its loop); bcrypt runs in a worker thread | NiceGUI's rules as they are; one copy of the check; the constant-time compare is not weaker | Rate limiting (none today; a new feature) | Low |
| 119 | Admin password reset finds the room by slug in the write transaction (`reset_room_password_by_slug`); a gone room is 404 `room_unavailable` with NiceGUI's "Room changed or no longer exists; refresh and try again". New password rules are `check_new_room_password` (blank refused, saved as typed, at most 72 bytes; NiceGUI fails with an unhandled bcrypt error there). Every token of the room is revoked; the room's streams are woken after the answer (NiceGUI wakes all streams). NiceGUI's reset keeps its own room id + slug check | The API names rooms by slug everywhere; slugs have a random part, so a new room never takes an old slug's place | Send the room id | Low |
| 120 | "Create New Room" on the admin page is part of 3.3 (NiceGUI's admin page has it; no other step covers it). `create_room` rules unchanged (trimmed name not empty, password not empty, saved as typed); a password over 72 bytes is 422 with the change-password message (`check_password_length`, before `create_room`; NiceGUI shows bcrypt's own message). Creating does not sign the admin in to the room. Invitations on the same NiceGUI page stay in 3.4 | Svelte must do everything NiceGUI does; the overview is where NiceGUI has it | A step of its own | Low |
| 121 | Admin API tests serve the API router from a small FastAPI app with NiceGUI's session and request-tracking middleware (`tests/test_api_admin.py`); the global test setup stays as it is. **Worth knowing:** in production, NiceGUI's middleware also sets its `session` cookie on the first API response of a browser (before this step too), so "the share endpoints set no cookies" holds for room cookies only | Enabling the middleware for all tests broke 13 tests that check the exact cookies a response sets | Add the middleware for every test and change those 13 tests | Low |
| 122 | Svelte admin is one page, `/app/admin`: the sign-in prompt, or the overview when signed in (NiceGUI: `/admin` and `/admin/login`). The start page gets NiceGUI's "Admin" button (decision 72 had none yet). NiceGUI's texts: "Enter Admin Password", "Admin Password", "Log in", "Wrong password" (under the field, like the room prompt), "Create New Room", "Refresh rooms", "No rooms yet. Create your first one!", "New Room" / "Room name" / "Password" / "Create", "Room created", "Admin Reset: X" / "New Room Password" / "Reset", "Password reset successfully". The key button is named "Reset password of X". An `admin_required` answer (signed out in another tab) shows "Admin sign-in required" and the sign-in prompt | Same flow as NiceGUI; one route needs no redirect logic | A separate `/app/admin/login` route | Low |
| 123 | Room links on the admin page (and a new room) open `/app/room/{slug}?admin=true`, as NiceGUI. The room page then asks `GET /admin/session`; when signed in it shows a "Back to admin" arrow in place of "ListR", and deleting the room goes back to `/app/admin`. It never gives access: without a room token the password prompt shows, as in NiceGUI | NiceGUI's admin navigation; the flag only changes links | No way back to admin | Low |
| 124 | `ActionResult` and `failed()` moved from `lib/data/index.ts` to `lib/data/result.ts`; admin calls live in `lib/data/admin.ts`, exported as the namespace `admin` from the data layer index. Admin data has no store: the overview reloads after a create or reset and on "Refresh rooms" (NiceGUI the same) | Admin is online-only and small; the room store's offline design is not needed | A reactive admin store | Low |
| 125 | The admin browser tests block service workers. **Worth knowing:** after a NiceGUI page installed its service worker, Playwright's WebKit sent the page loads it forwards without cookies, so NiceGUI's middleware started a new session and the admin sign-in seemed gone (found by these tests; fine in Chromium and Firefox). Real Safari is not known to do this: NiceGUI's own sign-ins work on the iPhone. The old service worker goes in 4.3 | The tests check admin, not NiceGUI's service worker; Svelte has none yet | Keep NiceGUI visits out of the admin tests | Low |
| 126 | Invitation API: admins use `GET`/`POST /api/v1/admin/invitations` and `POST …/{id}/revoke` (`{}` bodies); anyone with a link uses `GET /api/v1/invitations/{token}` and `POST …/{token}/rooms`. The integer invitation `id` is sent (NiceGUI shows "Invitation #N"; it is no secret and not a list or item). The server sends `status` (`active`, `revoked`, `expired`) from `invitation_status` in `src/room_invitations.py`, which NiceGUI's admin page now uses too; times are UTC ISO strings. Revoking an unknown or revoked invitation is 200 with no change, and listing deletes records inactive for 7 days (a `GET` that does housekeeping), both as NiceGUI | One copy of each rule; the client never judges expiry by its own clock | `DELETE` for revoke; `uid`s for invitations; status worked out in the browser | Low |
| 127 | A link that cannot create a room is 404 `invitation_unavailable` with NiceGUI's "This invitation is invalid or no longer active.", identical for unknown, expired, revoked and deleted. Creating is its own endpoint, not an op (a password in the body, as decision 101). Name and password errors are 422 with the messages of `create_room_from_invitation`, which also checks the invitation again inside the write transaction. No cookie is set: the creator signs in next, as in NiceGUI | NiceGUI's rules as they are; nothing about the room is told to a stranger | 401 like `share_unavailable`; sign the creator in | Low |
| 128 | Svelte UI with NiceGUI's texts. `/app/admin` gets a "Room invitations" section under the rooms: "Generate 7-day invitation", then an "Invitation #N" dialog with the "Invitation link" field and "Copy link" (the share dialog's copy helper); each row "Invitation #N: Active", "Created …", "Expires …" (UTC) and, when active, "Revoke" without asking first (named "Revoke invitation #N" for screen readers). The list reloads after issue and revoke. `/app/create-room/{token}` shows "Create your room" or the invalid-link text; "Passwords do not match" is checked in the browser; a link that stops working while the form is open gives a toast and disables "Create room"; after creating, the room page asks for the password. No "show password" button (NiceGUI has one; the room prompt has none). Links are `/app/create-room/{token}` until 4.2 | Same flow and places as NiceGUI | A confirm before revoke; sign in at once | Low |
| 129 | **Worth knowing:** NiceGUI's `/create-room/` sends `Referrer-Policy: no-referrer`; the Svelte page keeps the app-wide `same-origin` (decision 115). So the page's own file requests send the invitation URL as `Referer` to our server, which already has the token in the page path; other sites get no referrer, as before. `no-referrer` would make the create `POST` fail the same-origin check (`Origin: null`). Not changed: a per-request `referrerPolicy` plus `no-referrer` on this page | Nothing leaves our server; the token is in access logs either way (docs/room-invitations.md) | `no-referrer` meta on this page and `referrerPolicy: 'same-origin'` on each API call | Low |
| 130 | Test helpers: the `admin_app` fixture moved to `tests/conftest.py` and the admin client helpers to `tests/api_helpers.py`; `ADMIN_PHONE` and `admin_sign_in` moved to `browser_tests/svelte_app.py` | Admin and invitation tests share them; importing a fixture into a module trips Ruff's redefinition check | Copy them | Low |
| 131 | Svelte install manifests are made by Python at `/app/manifest.webmanifest` (`start_url` `/app/`) and `/app/room-manifest/{slug}.webmanifest` (`/app/room/{slug}`), both copies of NiceGUI's `src/static/manifest.json` with only `start_url` changed (shared `src/install_manifest.py`; NiceGUI's room manifest now uses it, same output). `id` and `scope` stay `/`; same headers as NiceGUI (`no-store`), as `application/manifest+json`. NiceGUI's `/manifest.json` is untouched. The Vite dev server forwards both and `/static/icons/` to Python | One app identity across both UIs and after the move to `/` (4.2 only drops the base); one copy of the manifest | A static file in `frontend/static/`; `scope: "/app/"` (a second app identity) | Low |
| 132 | **Worth knowing:** the Svelte room manifest does not check that the room exists (NiceGUI: 404, and its page links the default manifest for an unknown room). A deleted room's icon opens its password prompt, and signing in says "Wrong room or password." instead of "Room not found"; it never opens another room | The Svelte app never tells whether a room exists (decisions 18, 72/73); NiceGUI's own 404 is unchanged | Copy the 404 (an existence check through the manifest) | Low |
| 133 | One `<link rel="manifest">` in the root layout, chosen by the pure `manifestHref(route id, params, base)` (`lib/install/manifest.ts`) and changed on client-side navigation. Only `/room/[slug]` gets the room manifest (also on its password prompt and with `?admin=true`, which is never in the address); the list page `/room/[slug]/list/[list]` gets the default one, as NiceGUI's list pages and its help text ("install while viewing your room, not a list") | Same launch rules as NiceGUI; a pure function is easy to test | A `<svelte:head>` link per page (two links on room pages) | Low |
| 134 | `app.html` gets NiceGUI's icons from `/static/icons/` (apple-touch-icon 180, favicon 32 and 16; the Svelte starter `favicon.svg` is gone) and `apple-mobile-web-app-capable` / `apple-mobile-web-app-status-bar-style: black`, as NiceGUI. No `theme-color` meta yet (the Svelte colors differ; 3.6 and the backlog's theme-color item); the manifest keeps NiceGUI's colors | One copy of the icon files, already served at the conventional root paths too | Copy the icons into `frontend/static/` | Low |
| 135 | "Add to Home Screen" sits in the room menu right after "Share Room", as NiceGUI, and opens "Add ListR to your home screen" with NiceGUI's install help text and "Close" (`lib/install/InstallHelpDialog.svelte`); the text scrolls inside the dialog on a short screen | Decision 106; same place and words as NiceGUI | A help page | Low |
| 136 | Names stay unique ignoring case (Gate A): this already holds for Svelte, because the API calls the same helpers as NiceGUI. No code change; `tests/test_api_name_case.py` checks every name write with Norwegian letters (SQLite `NOCASE` folds only A–Z): list names compare with `casefold`, item names are saved in lowercase, tags stay case-sensitive (decision 57, confirmed at Gate A), room names need not be unique (decision 100). **Worth knowing:** rows saved before these rules may already differ only in case; they are left as they are (no data rewrite, no new index) | NiceGUI's rule is already case-insensitive; rewriting user data is a hard stop | A migration with a Unicode-aware unique index that merges or renames old duplicates | Low |
| 137 | Dark mode: NiceGUI's "Toggle dark mode" button (moon icon, its tooltip and its "Theme could not be saved on this device" warning), saved under NiceGUI's `listapp_theme` key, so the choice is shared with NiceGUI on the same site and never with the room. Without a saved choice the page follows the system (NiceGUI: light), also when the system changes. `app.html` sets `data-theme` before the first paint, as NiceGUI does. The button sits in the top bar of the room, list, share and admin pages; other pages show it above the page (NiceGUI: fixed at the top right of every page, which would cover the ⋮ menus on a phone). It has `aria-pressed` | Same control and storage as NiceGUI; the system default is what the owner tested at Gate A | Follow the system only; NiceGUI's fixed corner button | Low |
| 138 | One `theme-color` meta tag, set to the page background of the current mode (`#f4f5f7` / `#111418`) and updated on every switch. NiceGUI uses its blue `#1976d2`; the manifest keeps NiceGUI's colors. Ends the "no `theme-color` yet" of decision 134. Whether Safari's bars now follow a switch at once needs the iPhone (backlog, Manual checks) | The bars match the page in both modes, and the tag follows the toggle | Two tags with `media` (cannot follow the toggle); NiceGUI's blue | Low |
| 139 | Contrast: `frontend/src/app-colors.test.ts` reads `app.css` and checks WCAG AA in both modes (4.5:1 for text, 3:1 for field edges and focus). New `--control-border` for field edges and the switch track (was `--border`, 1.4:1); light tag blue `#1976d2` → `#1565c0` and orange `#e65100` → `#c43e00` (were 4.2:1 and 3.5:1 on the page). Decision 90's "Material 700 shades" now has these two exceptions | Tags are small outlined text on the page background | Keep the colors | Low |
| 140 | Accessibility pass. The add field is an ARIA combobox (suggestions are a `listbox` of `option`s; the browser tests use those roles now). A dialog the page closes (after Save) gives the focus back to the button that opened it, as Escape already did. The chosen hide mode shows its focus ring. Sliding switches do not move with Reduce motion. Zoom stays allowed (NiceGUI's viewport has `user-scalable=no`; not copied). Checked and kept: labels on all fields, errors as `alert`, headings, toasts as a live region; a browser test checks that every visible control has a name. No other small NiceGUI difference was found beyond decision 98 and the dark mode button | Keyboard and screen reader use without new features | Leave the ARIA as it was | Low |
| 141 | Toast layout check (`browser_tests/test_svelte_toasts.py`): each toast at most 48 px high and inside the screen, the toast area no taller than its toasts, with a long message, three stacked toasts, an open dialog and an 844×390 screen. Over a dialog it compares one screenshot pixel with the toast color. **Worth knowing:** a modal `<dialog>` makes the rest of the page inert, also the toast popover above it, so a toast's buttons cannot be pressed while a dialog is open: a tap on a warning toast's × lands outside the dialog and closes it (typed text is lost); the toast stays. Checked by hand in all three engines. Not changed: no "Undo" toast shows over a dialog (the item dialog closes first), and a warning goes by itself after 4 s; for the owner to decide | A hit test (`elementFromPoint`) skips inert elements, so it cannot tell above from below | Move the toasts into each open dialog | Low |
| 142 | Svelte stale-action tests hold back the page's live stream (a route that never answers) instead of delaying single updates, and prove the action was sent by its `…/ops` answer (`rejected`, or 401). The deleted-list matrix keeps NiceGUI's 6 actions with the role alternated per engine | The Svelte page learns about changes only through the stream; the op answer is the server's own verdict | Delay the SSE body; check DB only | Low |
| 143 | Not ported: NiceGUI's service worker checks in the restart test (Svelte has none until 5.1; 5.5 tests it). The Svelte restart test checks that an open page reconnects without a reload (NiceGUI reloads), with a 30 s wait for the stream's retries. The NiceGUI tests stay unchanged until 4.3 | Different internals, same user-visible rules | Port the service worker checks with 5.1 | Low |
| 144 | Owner (2026-10-06): admin sign-in gets its own cookie like the room cookie (`__Host-`, `Secure` on HTTPS, HTTP-only); a changed `APP_PASSWORD` ends all admin sessions. Built in Milestone 4 (step 4.0), before 4.3 removes NiceGUI's session storage. Replaces 117 from then on | NiceGUI's session goes away in 4.3, so admin sign-in is rebuilt anyway; the room cookie already shows the pattern | Copy NiceGUI's session as is; also rate limiting (skipped; user profiles stay in the backlog Ideas) | Low |
| 145 | Owner (2026-10-06): fix the toast issue from 141 in Milestone 4 (step 4.0): tapping a toast's × while a dialog is open must not close the dialog | Losing typed text is a bug users remember; small fix | Backlog; ignore | Low |
| 146 | Owner (2026-10-06): the share page shows "back to room" and "Reset share link" when this browser has access to the list's room, as NiceGUI. Without room access it reveals nothing about the room (test). Built in Milestone 4 (step 4.0). Replaces 113 | A partner who sends a share link to a room member should not strand them on the share page | Keep 113 | Low |
| 147 | Owner (2026-10-06): per-list change tracking for share links (fixes the timing signal in 108 and stops refreshes for other lists' changes) is decided and gets built in Milestone 5 or 6; 6.1 designs how, not whether | Fewer refreshes; a link visitor learns nothing about other lists | Keep 108 | Medium (migration) |
| 148 | Owner check (2026-10-06): the newest local production backup (2026-10-04; 11 rooms, 22 lists, 314 items), opened read-only, has no list or item names that differ only in case, and every item name is lowercase. Closes the open question in 136 | Read-only check on a copy | Download a fresh Railway copy | None |
| 149 | Owner phone test (2026-10-06), built in step 4.0: "Log out" into the room ⋮ menu; "Back to admin" follows the admin sign-in, not `?admin=true`; the admin key button and dialog say clearly that they reset the room password; list name in the top bar between the back arrow and the menus, dark mode into the ⋮ menu, list options stay outside. Not new features, only layout and text. Admin delete room and a bottom toolbar go to the backlog | Small, visible fixes; best before users see the new app | Backlog after the switch | Low |
| 150 | Step 4.0, admin cookie (implements 144): cookie `__Host-listapp-admin` on HTTPS, `listapp-admin` on plain HTTP (as the room cookie), HTTP-only, `SameSite=Lax`, Path `/`, 14 days (NiceGUI's old length). Value is a stateless token `v1.<expiry>.<nonce>.<hmac-sha256>`, key = current `APP_PASSWORD` with a domain-separation prefix, compared in constant time; a changed password ends all sessions. Sign-out only clears the cookie in this browser (a copied cookie would stay valid until it expires or the password changes). `GET /api/v1/admin/session` stays the "signed in as admin" status endpoint (no contract change, no frontend change). The Svelte admin no longer touches NiceGUI storage; NiceGUI's `/admin` keeps its own sign-in, so the two no longer share it (browser tests updated). Replaces 117 | Stateless means no new table or migration, and the password key gives the required reset. An expiry in the token bounds a stolen cookie | A server-side session table (allows real sign-out of every browser; needs a migration); a fixed HMAC of the password (never expires, same value for everyone) | Low |
| 151 | Step 4.0, toasts over a dialog (implements 145; fixes the problem in 141): the newest open `Dialog` draws the toast area inside itself (`Toast` with a `dialogId`; `toasts.dialogs` is the stack), and the page-level area draws nothing while a dialog is open. A popover inside a modal dialog is not inert, so × and action buttons work and a tap no longer reaches the backdrop. Toasts go back to the page when the dialog closes. The toast layout test in 141 still passes unchanged | The only DOM place a modal dialog leaves clickable is its own subtree. Inside the dialog the toast buttons are also in the keyboard focus trap | Move one shared area in and out of dialogs by hand (Svelte removes the dialog with it); close toasts on dialog open | Low |
| 152 | Step 4.0, share page room links (implements 146, replaces 113): `GET /share/{token}/changes` fills the feed's `room` with `{slug, name}` only when the request's cookie for the list's room is valid (checked in the same transaction: room looked up from the link, then the cookie of that slug); otherwise `room: null`, and nothing else in share answers names the room. The page shows the back arrow and "Reset share link" when `store.room` is set, keeps the slug after the list goes away so the reset message can offer "Back to room", and follows the new token after a reset (NiceGUI also moves on after a reset). `ShareApi.resetShareLink` calls the room's own reset endpoint with the slug from the last feed, so room cookie and same-origin rules are the room endpoint's. A browser that has the room cookie learns the room name and slug of a link it holds; it could read them anyway | No new endpoint or field: the existing `room` field in the feed is the "who is this room" slot; the check is server-side, so the page cannot be tricked by a client flag | A separate `GET /share/{token}/room` call; a `member` flag plus a second room lookup | Low |
| 153 | Step 4.0, phone test fixes (implements 149): "Log out" is the last entry of the room ⋮ menu (after a divider). "Back to admin" shows whenever `admin.signedIn()` (`GET /api/v1/admin/session`) is true, checked again when the room slug changes; `?admin=true` still appears in admin's room links but no longer matters (`openedFromAdmin` removed). The admin key button reads "Reset password" (its accessible name stays "Reset password of {room}"). Its dialog is titled "Admin reset of room password: {room}" and says what really happens: the server deletes every access token of the room, so all signed-in devices are logged out and need the new password; share links are not touched (checked in `reset_room_password_by_slug` and `tests/test_api_admin.py`). List top bar: back arrow, list name (`h1`, one line, "…" when long, full name in `title`), Options, ⋮; the dark mode switch is a "Dark mode" entry (`ThemeMenuItem`) in the list menu, so the share page has it too, and it counts as a top-bar toggle so the layout adds no second button. The room page keeps its dark mode button in the bar. The entry has `aria-pressed` for its state | Smallest change that follows the owner's list; the admin session endpoint was built for this | Keep the query as a second trigger (stale links would show a link that the cookie check should decide); a dark mode toggle in a second menu on the room page (not asked) | Low |

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
- [x] **Gate A: owner prototype review** (2026-10-05: continue; see the [Gate A checklist](#gate-a-checklist))

Milestone 3: rest of the app
- [x] 3.0 Official shutdown timeout for SSE (`src/main.py`, `src/api/events.py`, [`tests/test_server_shutdown.py`](../tests/test_server_shutdown.py), browser test server in `browser_tests/conftest.py`; decision 99, replaces 61)
- [x] 3.1 Room management (`room.rename` in `src/api/ops.py`, `src/api/room.py`, `_locked` helpers in `src/database_crud.py`, `frontend/src/lib/room/{RoomMenu,ChangePasswordDialog,DeleteRoomDialog}.svelte`, data layer `index.ts`/`api.ts`; [`tests/test_api_room.py`](../tests/test_api_room.py), `browser_tests/test_svelte_room_management.py`; decisions 100–106)
- [x] 3.2 Public share links (`src/api/share.py`, share access in `src/api/access.py`, `OpScope` in `src/api/ops.py`, share stream in `src/api/events.py`, helpers in `src/database_crud.py`; data layer `share.ts`, `openShare`; `lib/list/{ListView,ListMenu}.svelte`, `lib/ui/{MenuButton,ShareDialog}.svelte`, `lib/ui/share.ts`, `routes/share/[token]/`; [`tests/test_api_share.py`](../tests/test_api_share.py), `browser_tests/test_svelte_share.py`; decisions 107–116)
- [x] 3.3 Admin (`src/api/admin.py`, `src/admin_access.py` (password check shared with NiceGUI), `reset_room_password_by_slug` / `check_password_length` in `src/database_crud.py`; data layer `admin.ts`, `result.ts`; `lib/admin/`, `routes/admin/`, "Admin" on the start page, "Back to admin" on the room page; [`tests/test_api_admin.py`](../tests/test_api_admin.py), `browser_tests/test_svelte_admin.py`; decisions 117–125. Includes NiceGUI's "Create New Room"; creation invitations on the same NiceGUI page are left to 3.4)
- [x] 3.4 Creation invitations (`src/api/invitations.py`, `invitation_status` in `src/room_invitations.py` (shared with NiceGUI); data layer `invitation.ts` and invitation calls in `admin.ts`; `lib/admin/{AdminInvitations,InvitationDialog}.svelte`, `invitations.ts`, `lib/invitation/CreateRoomForm.svelte`, `routes/create-room/[token]/`; [`tests/test_api_invitations.py`](../tests/test_api_invitations.py), `browser_tests/test_svelte_invitations.py`; decisions 126–130)
- [x] 3.5 Home-screen install (manifest routes in `src/svelte_frontend.py`, shared `src/install_manifest.py`; `lib/install/{manifest.ts,InstallHelpDialog.svelte}`, manifest link in `routes/+layout.svelte`, icons in `app.html`, "Add to Home Screen" in `RoomMenu.svelte`; [`tests/test_svelte_install.py`](../tests/test_svelte_install.py), `browser_tests/test_svelte_install.py`; no service worker (5.1); iPhone check in the backlog; decisions 131–135)
- [x] 3.6 Theme, UX and accessibility (dark mode button in `lib/ui/{theme.ts,theme.svelte.ts,ThemeToggle.svelte}`, `app.html`, `app.css`; combobox in `AddItem.svelte`, focus return in `Dialog.svelte`; tests `tests/test_api_name_case.py`, `src/app-colors.test.ts`, `browser_tests/test_svelte_{theme,accessibility}.py`; names already unique ignoring case, no code change; decisions 136–140)
- [x] 3.7 Port remaining browser tests (incl. toast layout check) (`browser_tests/test_svelte_{toasts,deleted_lists,restart,hide_done}.py`, new tests in `test_svelte_share.py` and `test_svelte_live.py`; [port map](../docs/background/browser-test-port-map.md): 8 NiceGUI tests ported, 6 already covered, the service worker checks not applicable; no Svelte bug found; decisions 141–143)

Milestone 4: switch
- [x] 4.0 Owner decisions after Milestone 3: admin cookie (`src/admin_access.py`, `src/api/admin.py`, decision 150), toasts over a dialog (`lib/ui/{Dialog,Toast}.svelte`, 151), share page room links (`src/api/share.py`, `routes/share/[token]/`, 152), phone test fixes (153: room menu "Log out", "Back to admin" by admin sign-in, "Reset password" button and dialog text, list top bar with the name, dark mode in the list menu; `lib/room/{RoomHeader,RoomMenu}.svelte`, `lib/list/{ListHeader,ListMenu}.svelte`, `lib/ui/ThemeMenuItem.svelte`, `lib/admin/{AdminRooms,ResetPasswordDialog}.svelte`, `browser_tests/test_svelte_phone_fixes.py`). Tests: `tests/test_api_admin_session.py`, `tests/test_api_share.py`, `browser_tests/test_svelte_{admin,toasts,share,theme,rooms}.py`. Docs: `docs/api.md`, `docs/public-sharing.md`
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
