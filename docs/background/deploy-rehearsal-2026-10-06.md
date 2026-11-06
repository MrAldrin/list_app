# Deploy rehearsal, 2026-10-06

This was step 4.5 of the [Svelte rewrite record](svelte-frontend-rewrite.md).
It ran on the final tree (after 4.4), using the Dockerfile image and a copy of
the newest local production backup. The backup was taken 2026-10-04; its schema
version was 2. Nothing touched Railway or `main`. Only counts were recorded;
no names, passwords or tokens. The rehearsal scripts stayed outside the
repository (scratch directory), and the data copies were deleted.

## Result: all parts passed

| Part | Result |
| --- | --- |
| Backup copy | integrity ok, no foreign-key errors; 11 rooms, 22 lists, 314 items, 5 room tokens, 2 invitations |
| Migration 2 to 4 (code on a copy, and the container's own startup) | ok; counts unchanged; ids and legacy columns unchanged; 22/22 list uids and 314/314 item uids unique and set; new tables `deletions`, `processed_ops`, triggers and indexes added; log line `Database migrated from version 2 to 4`; pre-migration copy written and equal to the original |
| Image build | `podman build` of the Dockerfile ok |
| Pages | `/`, `/admin`, `/room/{slug}` (also `?admin=true`), `/list/{slug}`, `/share/{token}`, `/create-room/{token}` serve the Svelte shell; `/room/...` is `no-store` |
| Old URLs | `/admin/login` 308 to `/admin`; `/app/...` 308 keeps path and query; `/app/` to `/` |
| PWA files | `/sw.js` is the self-unregistering kill switch; `/manifest.webmanifest`, `/manifest.json`, `/room-manifest/x.webmanifest`, `/apple-touch-icon.png`, `/favicon.ico` all answer 200; POST to the removed `/_room-access/x` gives 405; unknown `/api/...` gives JSON 404 |
| API | admin 401/200, wrong password 401, POST without Origin refused, admin lists 11 rooms; disposable room: sign-in (wrong password refused), full snapshot feed, `list.create` and `item.add` applied, same `op_id` retried gives the identical stored answer, delta feed shows only the new item, live stream 200, share link works without a cookie |
| Restart | data and room cookie survive; no second migration; no journal file left |
| After the run | integrity ok, no foreign-key errors, version 4; rooms 11 to 12, lists 22 to 23, items 314 to 315 (the disposable ones); all original ids and names present |
| Real browser (Chromium headless, container) | open room, sign in, create list, add item, check it, reload keeps it checked, room page shows the list; 0 page errors |
| Rollback | `main` code refuses the migrated database ("newer than this app"; file unchanged); `main` code starts on the pre-migration copy |
| Full checks | ruff clean; pytest 1188 passed; vitest 294 passed (25 files); frontend format, lint, check, build ok; browser suite 165 passed (`-n 8`) |

The invitation count stayed at 2 after creating one: creating an invitation also
deletes expired ones.

## Session survival across the switch

For this test, `main`'s code (NiceGUI) ran on a backup copy. The setup used
`FORWARDED_ALLOW_IPS=*` so `X-Forwarded-Proto: https` counted. `main`'s own
functions created a disposable room and token. `main`'s `/_room-access/{slug}`
endpoint set the cookie (it answered 204). Then `main` stopped, and the new
container started on the same database file. It migrated 2 to 4.

- The new code read the old cookie, `__Host-listapp-room-<sha256(slug)>`.
  The changes feed answered 200 over HTTPS via the forwarded header. The cookie
  name and stored token stayed the same, so no one has to sign in to a room
  again.
- Without a cookie, the feed answered 401. The same `__Host-` cookie was not
  read over plain HTTP (401); plain HTTP uses differently named cookies. This
  affects local HTTP tests only.
- The owner still needed to verify whether Railway delivers
  `X-Forwarded-Proto` from a trusted address (below), and to test a real device.
- NiceGUI's own session cookie and the admin cookie are not carried over: admins
  sign in once on `/admin` after the switch.

## HTTPS detection and forwarded headers

- With `X-Forwarded-Proto: https` from a trusted proxy, room sign-in sets
  `__Host-listapp-room-...` and `__Host-listapp-last-room` with Secure, HttpOnly,
  `Path=/`, SameSite=Lax and no Domain. Without the header it sets the plain names.
- uvicorn trusts forwarded headers only from the addresses in
  `FORWARDED_ALLOW_IPS` (default `127.0.0.1`). In the container the default did
  not trust the header (it comes from the container bridge address, not loopback).
  `main` ran `uvicorn` through `ui.run` with the same default and no setting, and
  decision 160 keeps it. So the new code behaves like `main` here.
- `main`'s `/_room-access` endpoint refused requests that it did not see as
  HTTPS. Production remembered access therefore works only if Railway's proxy
  is trusted. This was not checked because the test did not touch Railway. The
  Gate B production check confirms it. If production room cookies have no
  `__Host-` prefix, set the Railway variable `FORWARDED_ALLOW_IPS=*` (the app is
  reachable only through Railway's proxy).

## Notes for the real deploy

- The rehearsal used the 2026-10-04 backup. Take a fresh backup right before the
  deploy (see [deployment](../deployment.md#backup-before-deploying)) and check its
  `pragma user_version` is still 2.
- Rollback after the switch needs both the old commit and the pre-migration
  database. Anything written after the switch is lost on restore.
