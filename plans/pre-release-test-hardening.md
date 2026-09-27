# Pre-release test hardening (proposed)

## Goal and boundaries

Build the strongest practical evidence for a chosen ListR release **before** a
Railway production deploy. This plan does not authorize implementation, merging,
pushing, accessing production data, or deployment. `main` remains owner-managed;
a push to a deployment-connected bookmark may trigger a redeploy. The feature
stacks (`dev`, `hide-checked-items`, `backup-offline-read-only`) are independently
rebased onto `main-staging`, **not integrated with each other**. Select which
features to ship before constructing and validating a release candidate.

The owner has an iPhone but no Mac or physical Android test phone. Installed-
iPhone acceptance is a [separate manual task](iphone-installed-offline-acceptance.md),
not part of this automated test-suite hardening work. Linux Playwright WebKit is
not installed iOS Safari, and an Android emulator is not a physical phone.
Never use live Railway or real user data for local test coverage.

## Execution order and approval boundaries

For the current task, design and implement disposable emulator/browser **test-
suite improvements** and run them on the relevant independent stacks. Report
failures rather than weakening assertions; changing application behavior requires
an explicit scope decision. Combining a release candidate, rehearsing a
production backup, starting a tunnel, deploying, and hands-on iPhone acceptance
are separate tasks with separate owner gates. See the
[installed-iPhone task](iphone-installed-offline-acceptance.md) for its procedure.
Physical Android acceptance remains pending without an Android phone.

## Proposed slices and evidence

1. **Freeze the candidate and test matrix.** Owner chooses whether the release
   contains only the Android test base, or which of the three feature stacks.
   Record exact jj change IDs and whether checks ran on each isolated stack or
   on a genuinely combined candidate. Review architecture and docs against the
   chosen code; resolve integration conflicts without losing backlog decisions.
   Do not assume results from separately tested stacks cover their combination.
2. **Offline device-like checks (only if offline ships).** Extend the offline
   branch's disposable `listapp_api35` test to force-stop Chrome and relaunch the
   *installed* room while server, ADB reverse and radio are unavailable. Verify
   the exact room and saved list/item details, a visible stale timestamp, no
   editing, and recovery. Then test reconnect with a second session changing
   data; distinguish temporary failure (keep old copy/time) from definitive
   room-password revocation/deletion (clear matching copy after reconnection).
   Add root-launch and fresh/no-copy cases where deterministic; do not weaken
   existing assertions to accommodate device quirks. Tests must use a fresh DB,
   disposable room, dedicated emulator, and restore ADB/network/server state in
   `finally`. Document Chrome/Android versions, scope, and any blocked scenario.
3. **HTTPS, browser storage and security.** Use a disposable *trusted local* TLS
   origin (not only a self-signed cert ignored by Playwright) for Chromium and
   Firefox: Secure/HttpOnly cookie-backed save, service-worker control, offline
   navigation, reconnection, denial/clearing, cache inspection for secrets, and
   error distinction. Keep the existing HTTP fallback tests. Evaluate whether
   emulator trusted-HTTPS setup is feasible without weakening certificate or
   Android security settings; if not, report Android HTTPS as unverified, not as
   an assumed pass. This does not test Railway's proxy; verify forwarded HTTPS
   scheme, cookie writes and WebSockets separately on an approved deployment.
4. **Database rehearsals (only for selected schema changes).** With the owner's
   approval, take a SQLite-consistent, access-restricted production backup as in
   [`docs/deployment.md`](../docs/deployment.md#sqlite-consistent-backups).
   Never point the candidate at the live DB. For `dev`, inspect case/space-
   insensitive duplicate item names on a *separate copy* and prove startup/index
   creation on a disposable copy or stop and agree a remediation. For
   `hide-checked-items`, rehearse schema migration/restart on a *different copy*,
   check integrity/foreign keys and compare representative rows/counts and
   completion defaults. If both ship, repeat on a third copy with the **combined
   candidate**. Keep backups, logs and data out of jj, tests, and public URLs;
   do not delete backups as a test cleanup.
5. **Combined candidate checks.** Once the owner selects a combination,
   run `uv run ruff format .`, `uv run ruff check --fix .`, `uv run pytest -q`,
   `uv run ruff format --check .`, `uv run ruff check .`, plus
   `uv run pytest browser_tests -q -n 0`; if offline is present run
   `node --test tests/test_offline_service_worker.test.mjs` and the relevant
   opt-in Android suite. Inspect the diff, resolve failures, and record exact
   commands/results. A test passing on an isolated branch is not a pass on the
   combined candidate. Finish these local checks before the owner's phone session.
6. **Separate manual iPhone task.** If offline ships, the owner may later
   authorize [installed-iPhone acceptance](iphone-installed-offline-acceptance.md).
   This is not an automated test-suite improvement or part of the current task.

## Owner decision before any release

- Choose the features/release candidate before combined validation. The
  [separate installed-iPhone task](iphone-installed-offline-acceptance.md) remains
  pending after automated/local checks. Installed iPhone and physical Android
  behavior remain unverified without real-device testing. Do not promise reliable
  offline shopping on untested devices.
- Decide how/when a private production backup can be provided for the schema
  rehearsals, without exposing it to tests, public hosting, or version control.
- Review the deployment checklist and rollback/restore readiness. Only the
  owner may authorize moving `main`, any push, Railway deployment, and the
  timing. Production smoke checks occur **after** an authorized deploy and do
  not count as pre-deploy evidence.

## Progress

- [x] Drafted plan against current documentation and independently rebased stacks.
- [ ] Owner chooses the release scope and accepts or revises the proposed gates.
- [x] Feasible local **offline automated-test hardening** on this independent stack: HTTP Chromium/Firefox offline revocation/deletion-on-reconnect; trusted local HTTPS cookie-backed offline navigation, generic-only cache contents, reachable 503 versus denial and IndexedDB write-failure recovery; Android 15 / Chrome 124 installed-room cold launch, root-address navigation, second-session edit on reconnect, transient outage and password-revocation/deletion clearing. `uv run pytest -q` passed 358 (8 known warnings), the full opt-in browser suite passed 70 with temporary profile-only NSS trust, Node service-worker checks passed 7, the full Android suite passed 4, and Ruff format/lint checks were clean. See the browser and Android testing guides for exact commands and limits. This is **not** combined-candidate or production evidence. Android trusted HTTPS lacks an approved profile-only trust mechanism; old root **icon** and fresh/no-copy **installed** launch remain unverified; immediate force-stop after fresh login can lose localStorage keys. Railway proxy, physical Android and installed iPhone remain unverified. Further device/security combinations are not claimed complete.
- [ ] Rehearse selected migrations on separate protected production-backup copies, after owner approval.
- [ ] Construct and verify the chosen combined release candidate, if applicable.
- [ ] Separate manual [installed-iPhone acceptance task](iphone-installed-offline-acceptance.md) pending; not part of automated test hardening.
- [ ] Owner makes a separate release decision, including explicit physical Android risk acceptance if offline ships.
