# Offline viewing: local implementation evidence

Current behavior is in [offline viewing](../offline-viewing.md). The implementation contract and remaining work are in
[Milestone 5](../../plans/svelte-frontend-rewrite.md#milestone-5-offline-viewing).
This record is local evidence, not production or iPhone verification.

## Scope and source

The owner approved all Milestone 5 work through local verification and Gate V
preparation. No deployment, bookmark moves, production changes, offline editing
or persisted edit queue are authorized. Continue the planning line above
`mqmmonus` / `5008e947`, descended from deployed `main` / `b7c411bc`.

## 5.1: complete app shell

Accepted source candidate: `wrzvvvxv` / `866d8bd6`. The initial Luna writer timed
out without a handoff; the parent preserved its partial diff and escalated to
Sol medium. Recovery found and fixed network-first navigation mixing a new
HTML shell with an old worker's assets. Controlled loads now use one complete
cached app version; updates wait for old controlled tabs to close. No forced
reload, `skipWaiting`, claim, API cache or shared-data cache was added.

The parent inspected worker/registration/config/server diffs and gate evidence.
The broad `/sw.js` kill switch remains unchanged. New registration waits for
legacy cleanup; `/service-worker.js` is JavaScript or 404, never the SPA fallback.

Worker-reported commands on the final source candidate:

- `cd frontend && npx tsc -p tsconfig.service-worker.json --noEmit && npm run format && npm run lint && npm run check && npm run test && npm run build`: green; 300 Vitest tests, no Svelte errors/warnings.
- `uv run pytest tests/test_pwa_routes.py tests/test_svelte_frontend_routes.py browser_tests/test_old_service_worker.py browser_tests/test_svelte_service_worker.py -q`: 87 passed.
- Full Python completion chain (`ruff format`, `ruff check --fix`, `pytest -q`, then format/lint checks): 1205 passed; Ruff clean.
- After the final browser assertion edit, targeted worker/takeover suite rerun: 15 passed across Chromium, Firefox and WebKit; changed Python test formatted/linted.

Update coverage changes actual built HTML and a real renamed/rewritten lazy
chunk, not only a worker version string. Complete A stays usable offline while
B waits; complete B works offline after adoption. Incomplete B retains A. Legacy
takeover and offline deep links use the built app and Python server.

## 5.2: unexposed snapshot adapter

Accepted isolated component: `owowntpn` / `012ee6d6e33a`, based on `mqmmonus`.
Only the adapter, direct unit tests and fake-indexeddb dev dependency changed.
A fresh Luna reviewer checked durable generations, room/share identity isolation,
privacy, corruption and failure behavior. The parent inspected the full adapter.

Two P2 findings were fixed by the parent with regression tests: reject pending
logout records whose canonical key disagrees with their room identity; validate
and delete corrupt routing metadata in the same transaction so cleanup cannot
erase a concurrent fresh save.

Parent ran the entire cheap frontend chain in the isolated workspace:
`npm run format && npm run lint && npm run check && npm run test && npm run build`.
All passed: 310 Vitest tests, no Svelte errors/warnings and successful build.
This is storage-only evidence, not offline UI or real-browser privacy acceptance.
The parent incorporated exactly the four reviewed storage files as change
`wnyuwrpo` and reran `npm ci`, worker TypeScript and the full frontend chain on
combined source: 314 Vitest tests, no Svelte errors/warnings, lint and build green.

Integration must capture generation before fetching, save only committed server
state and never retry a stale payload with a fresh token. Share snapshots strip
room metadata and contain one list. Local signout markers survive server logout
acknowledgment until explicit sign-in. Failed durable marker writes must still
clear visible data and be reported honestly. Cross-tab pending logout/sign-in
serialization remains an integration obligation.

## 5.3/5.4 accepted data component (not the complete milestone)

The parent accepted data component `onyomkmt` / `2d289575` after reviewing the
bounded repairs and their regression evidence.
It changes only the frontend data layer and its tests. Hydration is opt-in and
**disabled by default**; no offline page integration has been enabled.

The first candidate passed 326 unit tests but fresh privacy/regression reviewers
blocked it on late-response item-name disclosure, false completed-logout results,
a room-cookie failure clearing an independent share, and unsettled deleted-room
actions. A Sol repair fixed those and a stale-clear-hint race. Follow-up review
found a new share-operation deadlock from coupled feed/op generations, plus
logout message and resumed-queue status inaccuracies. A second bounded repair
separated feed invalidation from operation clearing, distinguished logout outcomes,
resynchronized retained queue counts, and tested reactive write-permission state.

Worker-reported round-two gate: focused 99 and 60-test subsets, full 341 Vitest
tests, frontend format/lint/check/build and separate worker TypeScript all green.
The parent inspected the round-two production diff and unchanged file boundary.
This is unit evidence, not integrated browser or device acceptance.

The owner delegated the fallback decision after clarification. The supervisor
chose fail-closed explicit sign-in when pending logout metadata cannot be read,
and honestly reported local-only logout where insecure LAN HTTP has no Web Locks.
HTTPS phone testing is recommended; localhost remains supported. These are
accepted MVP restrictions, not claims of complete logout or a permanent storage
guarantee. Already-authorized online use tolerates
unavailable snapshot storage. A local-only outcome must never claim server-cookie
revocation or confirmed persistent clearing. HTTPS/localhost coordination still
needs browser-runtime verification.

## Final local verification (UI, lifecycle, reconnect)

The interrupted UI checkpoint was completed in change `wvsyzxsw`. The earlier
Firefox "error loading dynamically imported module" teardown errors and the
unused-variable Ruff failures are resolved.

Final results (local only):

- Browser suite: 216 passed (`-n 4`; Chromium, Firefox, WebKit).
- Vitest 365 passed; Python 1205 passed.
- Ruff, frontend lint, svelte-check, build and worker `tsc` clean.

New browser tests: `test_svelte_offline.py` and
`test_svelte_offline_reconnect.py` (reconnect gating, other-device edits and
deletes, password-reset revocation, invalid share link, 5xx and network
failures keep the snapshot, resume), plus a logout-before-server-answers test
in `test_svelte_rooms.py`.

Root causes found:

- **Firefox teardown errors:** the test closed the page while the app was still
  starting, cancelling a lazy chunk import. Fixed in the tests (wait for idle),
  not by hiding the error. Helper: `wait_for_api_idle` in `conftest.py`.
- **Logout marker race:** the sign-out marker was stored after the password
  prompt appeared, so a quick reload could still show saved data. The marker is
  now stored first and the live feed stops at logout start.
- **Admin served from the shell:** 5.1 let the worker answer `/admin` and
  `/app` navigations from the cached shell, hiding admin and redirect pages.
  They are now network-only.
- **WebKit ignores `page.route` for worker-controlled pages:** tests that fake
  server answers must fake them differently (or before the worker controls the
  page).
- **WebKit cancelled-request page errors:** rare (about 1 in 12) teardown
  flake from cancelled in-flight requests in the rename-after-password-change
  test in `test_svelte_live.py`. Open; tracked in the backlog.

Not covered: a reload in the middle of a room DELETE (the marker is stored
before the DELETE by design), a compatibility-mismatch UI (not built), and any
real iPhone.

## Deployment prerequisite

Pre-worker tabs and uncontrolled first-install tabs cannot be retroactively
protected. The server serves only the current build; a later lazy request for
an old hashed chunk can return 404 after deployment. The first rollout must
resolve old-tab/asset handling before production approval. No prior-build
retention or Docker/Railway changes were made in this milestone. Local A→B tests
with an installed worker do not prove first-rollout safety.

## Remaining verification

Real iPhone Safari and home-screen behavior, OS and browser versions, and
production upgrade behavior have not been verified. See the
[Gate V guide](../../plans/offline-viewing-gate-v.md).
