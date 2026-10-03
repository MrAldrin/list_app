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
- **0.3** Write `docs/api.md`: endpoint list, request and response shapes,
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

### Milestone 3: the rest of the app

Goal: Svelte can do everything NiceGUI does. Start after Gate A.

- **3.1** Room management: rename room, change password, delete room.
- **3.2** Public share links: view and edit by token, reset link. Port the
  [public sharing](../docs/public-sharing.md) rules and their tests.
- **3.3** Admin: login, room overview, password reset.
- **3.4** Creation invitations: issue, revoke, create a room from a link.
- **3.5** Home-screen install: manifest, icons, launch URL rules from
  [home-screen installation](../docs/home-screen-installation.md).
- **3.6** Theme, small UX details and accessibility pass.
- **3.7** Port the remaining NiceGUI browser tests to Svelte versions.

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
  names and multiple devices. Pick the simplest safe rules; log them.
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

## Progress

Milestone 0: foundations
- [ ] 0.1 Frontend setup
- [ ] 0.2 Python serves `/app/`
- [ ] 0.3 API contract doc
- [ ] 0.4 Offline-ready schema migration
- [ ] 0.5 Writes bump `change_seq` and record deletions
- [ ] 0.6 README dev setup

Milestone 1: API
- [ ] 1.1 API package and access helper
- [ ] 1.2 Room session
- [ ] 1.3 Changes feed
- [ ] 1.4 List writes
- [ ] 1.5 Item writes
- [ ] 1.6 Tags and hide-done writes
- [ ] 1.7 Idempotent `op_id`
- [ ] 1.8 Live updates (SSE + NiceGUI bridge)
- [ ] 1.9 Concurrency tests

Milestone 2: prototype UI
- [ ] 2.1 Data layer
- [ ] 2.2 Room login and start page
- [ ] 2.3 Room page
- [ ] 2.4 List page: items, add, check
- [ ] 2.5 Quantity, edit, delete with undo
- [ ] 2.6 Tags and hide-done settings
- [ ] 2.7 Live updates and error states
- [ ] 2.8 Browser tests
- [ ] 2.9 iPhone test prep
- [ ] **Gate A: owner prototype review**

Milestone 3: rest of the app
- [ ] 3.1 Room management
- [ ] 3.2 Public share links
- [ ] 3.3 Admin
- [ ] 3.4 Creation invitations
- [ ] 3.5 Home-screen install
- [ ] 3.6 Theme, UX and accessibility
- [ ] 3.7 Port remaining browser tests

Milestone 4: switch
- [ ] 4.1 Production build
- [ ] 4.2 Svelte at `/`, old URLs kept
- [ ] 4.3 Remove NiceGUI
- [ ] 4.4 Docs update
- [ ] 4.5 Deploy rehearsal
- [ ] **Gate B: owner approves production switch**

Milestone 5: offline viewing
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
