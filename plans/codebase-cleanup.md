# Codebase cleanup

Lifecycle: tracked

Make the code smaller and easier to maintain: delete dead code, remove copies
(DRY), and adopt a few current idioms. No behavior changes unless a decision
below says so. Speed and memory matter little at about 4 users, so they come
last.

Source: a read-only review on 2026-10-15 by five reviewers (backend, frontend,
data/offline, tests/scripts, web research). Key claims were spot-checked by the
lead agent. Line numbers are from that date; re-check before editing.

## How we work

- One small item = one jj change. Run the Python checks from `AGENTS.md` and
  `npm test` / `npm run check` in `frontend/` after each code change.
- Browser suite once at the end of each phase, not per item.
- Do phases in order. Phase 1 makes later phases smaller.

## Decisions for you

- **D1. Visibility rules drift (architecture).** `ARCHITECTURE.md` says business
  rules live in Python and the frontend never copies them. In fact the
  hide-done rules run in `frontend/src/lib/data/visibility.ts`, and the Python
  copy `src/item_visibility.py` `filter_visible_items` is dead.
  (a) Keep client rules, delete the Python filter, update `ARCHITECTURE.md`.
  (b) Move filtering to the server.
  **Decided 2026-10-15: (a).** Hiding is a display rule and must run in the
  browser for offline viewing. The Python copy became dead when NiceGUI was
  removed. Doc fix: rules that change data live in Python; display rules such
  as hiding checked items run in the browser. Also fix `ARCHITECTURE.md:83`
  (`item_service.py`).
- **D2. Old migration code.** About 170 lines in `src/database_setup.py`
  migration 1 only run for pre-versioning databases. Production is at
  version 6. (A) keep, (B) build fresh databases from one final schema and keep
  migrations as history, (C) delete the version-0 branches.
  **Decided 2026-10-15: (C).** Low stakes; no local copy is at version 0 (local
  copies are at 4 and 5). Keep migrations 2-6 so those backups still restore.
  A fresh database must still build. Loading a version-0 file fails loudly and
  rolls back; it does not corrupt data.
- **D3. Session logic refactor.** Sign-in/sign-out is written twice in
  `frontend/src/lib/data/index.ts`, and the logout sequence five times. Merging
  is worth it but security-sensitive (effort L).
  **Decided 2026-10-15: do it, as the last step of Phase 5**, after the
  `index.ts` split. Low user count keeps the risk acceptable.
- **D4. `ty`.** Listed as a dev dependency but never run.
  **Decided 2026-10-15: keep it.** Fix its 5 findings (`api/errors.py`,
  `api/ops.py:533`) in Phase 2, then add `uv run ty check` to the Python checks
  in `AGENTS.md`. Drop it if the beta gives too many false alarms.
- **D5. `httpx2`.** `tests/test_server_shutdown.py` imports `httpx2 as httpx`.
  **Checked 2026-10-15: fine, no action.** Starlette's `TestClient` asks for
  `httpx2` (Pydantic's maintained fork of `httpx`). It was added on purpose on
  2026-09-29.

## Phase 1: delete dead code (low risk, big win)

- [x] [refactor] `src/database_crud.py`: delete about 50 functions only tests use
  (at least 39 confirmed; about 730 of 1729 lines), including the
  `expected_slug` checks and `*_with_room_token` wrappers. Port or delete the
  tests that use them as setup helpers.
- [x] [refactor] `src/item_service.py`: move `clamp_quantity` and the two used
  names into `src/api/ops.py`, delete the module. Simplify `item_edit`
  (`ops.py:405-419`) to reuse `_item_name`.
- [x] [refactor] D1: delete `src/item_visibility.py` `filter_visible_items` and
  its tests; update `ARCHITECTURE.md` (lines 83, 89), `docs/api.md:6` and the
  `visibility.ts` header comment.
- [x] [data] D2: delete the version-0-only branches of migration 1 in
  `src/database_setup.py` (slug backfill, list rebuild, items FK repair, legacy
  column `ALTER`s) and their tests. Check a fresh database still builds.
- [x] [refactor] `src/live_updates.py`: drop unused `register_listener` (keep
  `_listeners`; five test files use it as a hook).
- [x] [refactor] Frontend: drop test-only `RoomHandle.signedOut()`, simplify
  `events.ts` `#reconnected` branches, delete empty `src/lib/index.ts` and the
  bare `#lib` alias.
- [x] [test] Rename `browser_tests/test_svelte_install.py` (name clash with
  `tests/`), delete the NiceGUI leftover assertion in
  `tests/test_serve_svelte_local.py:35`.
- [x] [infra] `Dockerfile`: `uv sync --no-cache` so the uv cache stays out of
  the image.

## Phase 2: backend DRY and idioms

- [x] [refactor] One cookie module: shared set/clear helpers for room and admin
  cookies (`api/admin.py:58-78`, `api/session.py:42-62`, `api/room.py:67-68`).
  Security flags live in one place.
- [x] [refactor] Request models: a `StrictBody` base, a `Password` type and a
  `JsonBody` `Annotated` dependency. Enable Ruff `FAST` (15 hits) and
  `ASYNC210/230/251`.
- [ ] [refactor] One `hash_password()` and shared room-creation checks; make
  `room_invitations.py` call them (keep its messages unless agreed otherwise).
- [ ] [refactor] Small merges: stacked decorators in `pwa_routes.py`, one
  helper for the three error handlers in `api/errors.py`, one helper for
  `post_op`/`run_share_op`, single slug/UUID/token-hash helpers.
- [ ] [infra] D4: fix the 5 `ty` findings, then add `uv run ty check` to the
  Python checks in `AGENTS.md`.
- [ ] [refactor] A transaction context manager for the remaining hand-written
  BEGIN/commit/rollback blocks.

## Phase 3: test DRY

- [ ] [test] `tests/test_api_list_ops.py`: import from `api_helpers` instead of
  its copies; move `room` and `notified` fixtures to `conftest.py`.
- [ ] [test] One strict `assert_error` (five copies today); merge
  `set_cookies` / `plain_browser` copies.
- [ ] [test] Merge overlapping migration, manifest and route tests (keep unique
  assertions).
- [ ] [test] Frontend: move `json()` / `fakeFetch()` to `test-helpers.ts`.
  Browser tests: shared `share_link` and `hold_live_updates` in `svelte_app.py`;
  `wait_for_function` instead of sleep loops.
- [ ] [test] One Playwright-free server launcher shared by
  `test_server_shutdown.py` and `browser_tests/conftest.py`.

## Phase 4: frontend UI DRY

- [ ] [refactor] Move repeated CSS (`.actions` in 13 files, labels, forms,
  titles) to `app.css`.
- [ ] [refactor] One `PasswordPrompt` for `RoomLogin` and `AdminLogin`.
- [ ] [refactor] One `FormDialog` for the eight form dialogs.
- [ ] [refactor] One page shell for room, list and share pages (load, auth,
  error, connection status).
- [ ] [refactor] Shared helpers: share/copy with toast, undo toast, admin
  sign-out handling, `keepFocus`, theme-save notice. Move list search into a
  tested pure function.
- [ ] [refactor] Small components: `Brand`, `BackLink`, shared list-row style.

## Phase 5: data layer

- [ ] [refactor] `snapshot-store.ts`: one generation-bump helper (three copies);
  split pure validators and IndexedDB helpers into their own files.
- [ ] [refactor] `index.ts`: split messages, standalone session and a
  pending-logout helper into own files.
- [ ] [refactor] Small fixes: `#guardWrite()`, one try/result helper, one
  backoff constant, `room-store` `#load` reuse, clear `#sentAuthorization`
  on sign-out.
- [ ] [refactor] Service worker: run `discardUnusedVersions()` on activate and
  navigation only.
- [ ] [security] D3, last: one sign-in/sign-out path in `index.ts` (today two
  sign-in copies and five sign-out copies). Existing index and snapshot tests
  must stay green; add tests first if a path is uncovered.

## Not now

- FastAPI built-in SSE (`EventSourceResponse`, FastAPI 0.135+): removes our
  keep-alive code. Do it next time `src/api/events.py` changes.
- SQLite WAL: small gain, since `_DB_LOCK` serializes access anyway.
- Bounded handle registry, IndexedDB snapshot pruning, periodic op pruning,
  no import-time database open: real but tiny at about 4 users.
- Rejected: STRICT tables (table rebuild on live data), Svelte attachments (no
  actions to replace), SvelteKit remote functions (static SPA), dropping
  `python-dotenv`, Python 3.14.
- Spotted: `plans/test-suite-speed.md` Priority 4 first bullet is already done.

## Progress

- [x] Review done and findings checked (2026-10-15).
- [x] Decisions D1-D5 made (2026-10-15).
- [x] Phase 1
- [ ] Phase 2
- [ ] Phase 3
- [ ] Phase 4
- [ ] Phase 5
