# ListR performance and security review

Date: 2026-10-19. Scope: `src/`, `frontend/src/lib/service-worker.ts`, `Dockerfile`, `.dockerignore`, `frontend/build/`.
Method: code reading plus throwaway measurements. The benchmarks ran the real server (`src/main.py`, uvicorn, `APP_RELOAD=false`) on a temp DB under `scratchpad/bench/data/`. `list.db` and the repo were not changed. Production was not touched. Scripts: `scratchpad/bench/bench.py`, `bench2.py`, `bench3.py`, `bench4.py`, `fill.py`.

Note on measurements: single runs on a 16-core dev box, so treat them as orders of magnitude. The first benchmark runs used the `.env` value `APP_RELOAD=true` (local dev), which made RSS readings belong to the reloader parent. The RSS numbers below were re-measured with reload off.

## Measured numbers

| Item | Result |
|---|---|
| bcrypt cost (rounds 12, this machine) | about 186-190 ms per hash |
| Startup, fresh DB (migrations + Home room hash) | 0.46 s to first answer |
| Startup, DB with 1000 items | 0.26 s |
| Server RSS idle | about 56 MB |
| RSS with 100 open SSE streams | about 64 MB (about 40 KB per stream) |
| SSE cap | 100 streams; the 101st gets 503 |
| `item.add` (1000 sequential, no streams) | p50 7 ms, p95 22 ms |
| `item.set_done` (200 sequential) | p50 9 ms, p95 31 ms (0 streams); p50 20 ms, p95 39 ms (5 streams, one run, client noise likely) |
| Full changes feed, 1000 items | 283 KB raw, 35 KB gzip, p50 3.4 ms |
| Incremental feed, 1 change | 415 bytes |
| Full changes feed, worst room (100 lists x 1000 items = 100k items) | 27.2 MB, p50 410 ms with the DB lock held |
| Small GET queued behind one worst-case full feed | p50 380 ms |
| Server RSS, one worst-case full feed | 55 MB to 206 MB (peak 211 MB), transient |
| Legit GET p50, idle | 1.4 ms |
| Legit GET p50, 1 attacker thread doing sign-ins to random unknown room slugs (about 5 req/s) | 196 ms |
| Legit GET p50, 8 attacker threads (about 6.7 req/s) | 1495 ms (max 1500 ms) |
| Known room, wrong password, 11 tries | 401 x10, then 429 with no bcrypt cost (limiter works per slug) |
| Frontend build | 275 KB raw, 89 KB gzip total; JS 254 KB raw, 84 KB gzip |
| Runtime deps, installed site-packages | 34 MB (fastapi 0.140.0, starlette 1.3.1, uvicorn 0.51.0, pydantic-core, uvloop, httptools, bcrypt 5.0.0) |
| Dependency audit (pip-audit, 28 pinned runtime packages) | No known vulnerabilities |
| HMAC-SHA256 guessing (Python, one core) | about 0.88 M guesses/s |

Docker image size: not measured (no Docker on this box). The 34 MB above is the Python runtime layer only. The base image size is unknown.

---

## Ranked findings

### 1. Unauthenticated sign-ins hold the global DB lock while bcrypt runs (availability DoS)

- **Evidence:** `src/database_crud.py:933-955` (`authenticate_room_and_issue_token`) runs `_password_matches` (bcrypt) inside `transaction(write=True)`. That holds `_DB_LOCK` (`database_crud.py:27`, `38-52`). The dummy hash for unknown slugs (`:948-950`) is also under the lock. The sign-in route is `src/api/session.py:40-48`, a sync `def`, so it runs in the threadpool. Member paths also hold the lock during bcrypt: `change_room_password_locked` (`database_crud.py:1033-1050`, called from `src/api/room.py:41`) and `delete_room_with_password_locked` (`database_crud.py:1053-1064`, `room.py:69`).
- **Limiter gap:** the sign-in limiter is keyed by slug (`src/api/sign_in_limit.py:22-27`, `src/sign_in_limiter.py`). Random unknown slugs each get a fresh bucket, so there is no limit. There is no per-client-IP limit. The Origin check does not stop this: a script just sends `Origin`.
- **Attack scenario:** one script posts to `/api/v1/rooms/<random>/session` with `Origin: https://<app>` in a loop. Each request holds the one DB lock for about 190 ms. Measured: with one thread, every user's read waits about 200 ms. With eight threads, every read waits about 1.5 s. All 5 users see slow or failing syncs for as long as the script runs.
- **Likelihood and impact:** low to medium. It needs a script and the public URL. Impact is availability only; no data is exposed. Affects the whole app, not one room.
- **Proposal:** (a) Verify the password outside the lock: read the hash in a short read transaction, run bcrypt with no lock, then open a short write transaction that inserts the token only if `authorization_version` still matches. (b) Add a global failure bucket for unknown slugs, plus a per-client-IP bucket. `FORWARDED_ALLOW_IPS=*` (docs/deployment.md:27) gives the real client IP in `request.client`; verify this on Railway first. (c) Optionally cap concurrent bcrypt calls with a semaphore so threadpool threads cannot all wait on it.
- **Effort:** S to M (half a day with tests). **Risk:** low to medium. This touches the sign-in path, so add a race test for "password changed during sign-in". **Deps:** none. Cover with pytest and the browser sign-in tests.

### 2. No security headers beyond Referrer-Policy and nosniff on files

- **Evidence:** `src/svelte_frontend.py:64` (only `Referrer-Policy: same-origin`), `:70-77` (`nosniff` on files only). `src/api/requests.py` (`NoStoreMiddleware`) sets no security headers on API JSON. No CSP, no `X-Frame-Options`, no `frame-ancestors`, no HSTS, no `Permissions-Policy` in `src/`. The app shell has an inline theme script (`frontend/src/app.html`), which a CSP would need to hash. I found no `{@html}`, `innerHTML` or `eval` in `frontend/src` (non-test), so no XSS sink was found.
- **Attack scenario:** clickjacking of the room page: a third-party page frames the app. Impact is low, because SameSite=Lax cookies are not sent in cross-site frames, so the framed page is signed out. XSS, if one were ever added, would have no CSP backstop.
- **Proposal:** add a small ASGI middleware: `X-Content-Type-Options: nosniff` on API responses, `X-Frame-Options: DENY` plus `frame-ancestors 'none'`, and a CSP (`default-src 'self'`, `connect-src 'self'`, hashes for the inline script and SvelteKit bootstrap). Check HSTS at Railway's edge (not verified here; no prod access).
- **Impact:** defense in depth. **Effort:** S for frame and nosniff headers; M for a CSP that works with SvelteKit and the service worker. **Risk:** low for frame and nosniff; a CSP can break the app if wrong, so ship report-only first or rely on the browser tests. **Deps:** browser suite (Chromium, Firefox, WebKit).

### 3. Admin session key is the raw APP_PASSWORD; Home room starts with the same password

- **Evidence:** `src/admin_access.py:24-25`: the HMAC key is `APP_PASSWORD` itself, with no KDF or separate secret. The token is `v1.<expiry>.<nonce>.<sig>` with the payload in clear (`:33-35`). Lifetime 14 days and no server-side revoke (only a password change ends it). `src/database_setup.py:40`: the default "Home" room's password hash is made from `APP_PASSWORD` at creation.
- **Attack scenario:** an admin cookie is stolen (XSS, a shared device, a leaked HAR file). The attacker can then guess `APP_PASSWORD` offline. Measured guessing rate: about 0.88 M/s on one Python core, so an 8-character lowercase password falls in about 3 days of one core, and a dictionary word in seconds. Recovering the password gives room-reset and room-delete rights for the admin role.
- **Likelihood:** low; needs a stolen admin cookie. Impact: high if APP_PASSWORD is weak.
- **Proposal:** derive the signing key from a separate secret (for example HKDF over `APP_PASSWORD` with a fixed label, or a new env var). Changing it signs out admins once, which is acceptable. Check APP_PASSWORD strength (do not print it).
- **Effort:** S. **Risk:** low. **Deps:** none.

### 4. Room access tokens never expire on the server

- **Evidence:** `src/database_crud.py:567-582` checks `revoked_at IS NULL` and `authorization_version` only. No `created_at` or idle check. Cookie `MAX_AGE` is one year (`src/room_cookies.py:7`). Tokens are dropped only by password change or when 200 newer sign-ins arrive (`src/field_limits.py:MAX_SESSIONS_PER_ROOM`).
- **Attack scenario:** a phone with a room cookie is lost or sold. The cookie works until the room password changes or 200 later sign-ins push it out. There is no "sign out other devices" button in the API (`docs/api.md`).
- **Likelihood:** low. Impact: low for 5 users.
- **Proposal:** add an absolute lifetime (for example 180 days) and an idle timeout check in the token query. Optionally add a "sign out all devices" action (a password change already does this).
- **Effort:** S to M, plus a product call on the lifetime. **Risk:** low to medium (users may be signed out). **Deps:** sign-in tests.

### 5. Invitations allow unlimited room creation

- **Evidence:** `src/api/invitations.py` (public `POST /api/v1/invitations/{token}/rooms`) and `src/room_invitations.py:101-118`. The invitation is reusable for 7 days, with no count limit and no rate limit. Each call runs bcrypt outside the lock (`:109`), about 190 ms of CPU.
- **Attack scenario:** an invitation link leaks. The holder creates rooms in a loop (about 5 per second on one core), filling the DB and CPU. Also the room list fills with junk.
- **Likelihood:** low (needs a leaked invitation). **Impact:** low to medium.
- **Proposal:** cap rooms per invitation (for example 5), or count uses on the invitation row. Keep the bcrypt cost.
- **Effort:** S (one column plus check). **Risk:** low. **Deps:** `docs/room-invitations.md` update, tests.

### 6. Share tokens are stored in plain text

- **Evidence:** `lists.share_token TEXT` (`src/database_setup.py:122`). `rotate_share_token_locked` and `get_share_token_locked` store and read the raw token (`src/database_crud.py:136-147`). Room tokens and invitation tokens are hashed (`database_crud.py:894-905`, `room_invitations.py:35-37`). The deploy backup copies the whole DB (`scripts/deploy_backup.py`).
- **Attack scenario:** someone reads a backup or the DB file. Every share link in it gives public edit access to that list.
- **Likelihood:** low. Impact: medium (public edit of a list, not room access).
- **Note on the fix:** room members must still see the link (`GET .../share-link` returns the token), so a plain hash does not work. Options: encrypt at rest with a key from the environment, or accept the risk for a 5-user app.
- **Effort:** M (migration, backup check). **Risk:** medium (touches production data). **Deps:** deploy backup, `docs/public-sharing.md`.

### 7. Full changes feed has no size or memory bound; no compression

- **Evidence:** `src/api/changes.py:29-49` returns the whole room when `since=0`, when the client is ahead, or when behind pruned deletions. `src/database_crud.py:665-746` builds the row dicts inside the lock. No compression middleware in `src/` (checked).
- **Numbers:** 1000 items, 283 KB raw, 35 KB gzip. Worst allowed room (100 lists x 1000 items): 27 MB, 410 ms under the lock, about +150 MB RSS for one read.
- **Attack scenario:** a user with a valid cookie loads a full room in a loop. Each read holds the lock for about 0.4 s, and each response uses about 150 MB until freed. Only a member can do this, so it is mostly a self-inflicted or accidental risk.
- **Proposal:** (a) gzip `/changes` only (not SSE): about 8x smaller at 1000 items; (b) fetch rows under the lock but build dicts after releasing it; (c) later, paginate full snapshots by list.
- **Impact:** not a problem at today's size (1000 items is 3 ms). Becomes one near the 100-list cap. **Effort:** S for gzip; M for pagination. **Risk:** low. **Deps:** `docs/api.md` (changes feed).

### 8. Single DB connection behind a global re-entrant lock

- **Evidence:** `src/database_setup.py:625-653` (`_LazyConnection`, one `sqlite3.Connection`, `check_same_thread=False`, `timeout=1.0`), `src/database_crud.py:27` (`_DB_LOCK = threading.RLock()`), `:38-52`. Every read and write is serialized, including reads. Journal mode is the default rollback journal (`docs/deployment.md:122`).
- **Impact now:** fine. Writes take about 7 ms p50. Reads take about 1.5 ms. Serial access is enough for 5 users.
- **Proposal:** none now. If needed later: WAL with separate reader connections. The WAL note in `docs/background/sqlite-wal-timeout.md` says "keep WAL off" for now; revisit only with evidence.
- **Effort:** L. **Risk:** medium (backup and deploy scripts depend on rollback mode).

### 9. SSE fan-out: every write wakes every stream in the room

- **Evidence:** `src/live_updates.py` (`wake_streams`, `MAX_SUBSCRIPTIONS = 100` at `:94`); `src/api/events.py:84-100` (each stream does one threadpool read per wake, plus a 15 s recheck, `RECHECK_SECONDS` at `src/api/events.py:34`).
- **Numbers:** write p50 went from 9 ms to 20 ms with 5 streams (one noisy run). About 40 KB RSS per stream. At 100 streams the 101st gets 503.
- **Impact:** low at this scale. Also, one shared-token holder can use up slots (a share link can open streams). **Proposal:** none needed now. If ever needed, read the room seq once per write and send it to all streams. **Effort:** M. **Risk:** low.

### 10. Docker image runs as root and uses floating base tags

- **Evidence:** `Dockerfile:12-22`: final stage is `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`, no `USER`, and the tag is not pinned by digest. `node:24-slim` in the build stage. The build stage is discarded (good). `.dockerignore` excludes `list.db`, `.env`, `tests/`, `local_only/`, `frontend/build` and `node_modules` (good). `uv sync --locked --no-dev --no-cache` is correct.
- **Impact:** a bug in the app that gives code execution would run as root inside the container. The DB volume may have root-owned files; a non-root user needs write access to the volume.
- **Proposal:** add a non-root user, check the Railway volume ownership first, and pin base images by digest. **Effort:** S to M. **Risk:** medium (volume permissions can lock out the app; the deploy backup handles recovery per AGENTS.md).

### 11. Limiter is per slug, in memory, and resets on restart

- **Evidence:** `src/sign_in_limiter.py` (`ROOM_LIMIT = 10` per minute, `src/sign_in_limiter.py:22`); `src/api/sign_in_limit.py`. Measured: 10 wrong tries, then 429.
- **Impact:** guessing is capped at 10 per minute per room. A 4-digit PIN would take about 17 hours at full rate; a 4-letter lowercase password about a month. Legacy rooms may have shorter passwords (`docs/api.md`, room password rule). This needs the slug, which is in the URL the members use. Low risk for 5 users.
- **Proposal:** the per-IP bucket from finding 1 covers this too. **Effort:** part of finding 1. **Risk:** low.

### 12. APP_RELOAD in the local `.env`

- **Evidence:** `.env` has `APP_RELOAD=true` (local only, per `docs/deployment.md:26`). With reload on, the process is a supervisor with a child (RSS and watcher overhead).
- **Impact:** only matters if Railway sets it too. Not checked (no Railway access).
- **Proposal:** confirm the Railway variable is unset or `false`. **Effort:** trivial.

---

## Checked and fine

- **Same-origin writes:** `src/room_cookies.py:24-33` requires an exact `Origin` and `Sec-Fetch-Site` of none or same-origin. `src/api/requests.py` applies it router-wide, with JSON content type. This blocks browser CSRF. It is not an auth control for scripts (they can send any `Origin`), which is expected.
- **Cookies:** HttpOnly, SameSite=Lax, Path=/, Secure over HTTPS, `__Host-` prefix (`src/api/cookies.py`).
- **Token entropy:** `secrets.token_urlsafe(32)` (256 bits) for room, share and invitation tokens. Invitation room slugs use 18 bytes (144 bits). Room and invitation tokens are stored as SHA-256 (`database_crud.py:894-905`).
- **Timing:** unknown-room sign-in spends a bcrypt (`database_crud.py:948-950`). Admin password compare is constant time (`admin_access.py:50-57`, `hmac.compare_digest`).
- **Passwords:** bcrypt; 72-byte and 1024-char limits (`field_limits.py`, `docs/api.md`).
- **Input limits:** 64 KB body cap with 413 (`src/api/requests.py`). Name, description and count limits in `field_limits.py`. Strict pydantic models forbid unknown fields.
- **Path handling:** SPA catch-all rejects `..` and backslashes and resolves inside the build dir (`src/svelte_frontend.py:131-146`). `/api` and `/static` are excluded from the catch-all.
- **Logging:** `log_level="warning"` (`src/main.py`), so share tokens are not logged by uvicorn access logs.
- **Docs and OpenAPI:** disabled (`src/server.py`).
- **Admin surface:** admin can list rooms, reset passwords and delete rooms without the room password. This is documented as a design choice. Admin sign-in grants no room access (`src/api/admin.py`).
- **Service worker:** precaches all immutable assets at install and serves the shell from cache. Only complete installs become active (`frontend/src/service-worker.ts`). API paths are never cached. Cache names are versioned. Fine for this app.
- **Frontend data:** the client reads incrementally with `since=<seq>` (`frontend/src/lib/data/room-store.svelte.ts`). The only interval is a one-minute clock tick (`ListView.svelte:97`). No token in localStorage (only the theme key).
- **Dependencies:** pip-audit found nothing for the pinned runtime set. Dev-only packages (playwright, cairosvg, ty) are not in the image and were not audited.

## Open questions and not checked

- Railway edge headers (HSTS, others) and the real value of `FORWARDED_ALLOW_IPS` and `APP_RELOAD` on Railway: not verified (no prod access, and not run here).
- Docker image size: not built.
- APP_PASSWORD strength: not checked (secret; not printed).
- Old Svelte/NiceGUI history in `docs/background/sqlite-wal-timeout.md` still says DB calls run on the NiceGUI event loop. That is history, but the doc may confuse readers.

---

## Top 3 picks

1. **Finding 1: stop bcrypt under the DB lock and add per-IP and unknown-slug limits on sign-in.** Measured: one script takes all reads from about 1.5 ms to about 200 ms (one thread) or about 1.5 s (eight threads). Effort S to M. Risk low to medium. Needs a race test. No dependencies.
2. **Finding 2: add frame and nosniff headers now; CSP after.** Cheap. Effort S for the first part. Risk low. Defense in depth.
3. **Finding 7 (gzip part) with the lock-free dict build.** Cuts the 1000-item feed from 283 KB to 35 KB and shortens lock hold for large rooms. Effort S. Risk low. Not urgent at 5 users.

Next after these: finding 3 (separate admin signing key), finding 4 (room token lifetime, needs a product call), finding 5 (invitation room cap).
