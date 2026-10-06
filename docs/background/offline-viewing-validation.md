# Offline viewing: local implementation evidence

Current behavior will be documented in the offline viewing guide when integration
is accepted. The implementation contract and remaining work are in
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

## Deployment prerequisite

Pre-worker tabs and uncontrolled first-install tabs cannot be retroactively
protected. The server serves only the current build; a later lazy request for
an old hashed chunk can return 404 after deployment. The first rollout must
resolve old-tab/asset handling before production approval. No prior-build
retention or Docker/Railway changes were made in this milestone. Local A→B tests
with an installed worker do not prove first-rollout safety.

## Remaining verification

Data/UI/privacy integration, the final browser acceptance suite and Gate V
checklist remain unfinished. Real iPhone Safari/home-screen behavior, OS/browser
versions, and production upgrade behavior have not been verified.
