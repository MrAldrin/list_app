# Pre-release test hardening (proposed)

## Goal and boundaries

Build the strongest practical evidence for a chosen ListR release **before** a
Railway production deploy. This plan does not authorize implementation, merging,
pushing, accessing production data, or deployment. `main` remains owner-managed;
a push to a deployment-connected bookmark may trigger a redeploy. The feature
stacks (`dev`, `hide-checked-items`, `backup-offline-read-only`) are independently
rebased onto `main-staging`, **not integrated with each other**. Select which
features to ship before constructing and validating a release candidate.

The owner has an iPhone but no Mac or physical Android test phone. **Manual
installed-iPhone testing is possible without a Mac** using Safari and a reachable
HTTPS test URL. A Mac is needed for iOS Simulator/Safari remote inspection, not
for the manual acceptance flow. Linux Playwright WebKit is not installed iOS
Safari, and an Android emulator is not a physical phone. A separate
non-production Railway HTTPS deployment could test proxy behavior if the owner
approves its cost and setup, but is not required for the iPhone check: a
short-lived HTTPS tunnel to a disposable local server is an alternative. Never
use live Railway or real user data merely to make the phone test reachable.

## Execution order and approval boundaries

Complete **all automated/local tasks that need no human review first**: design
and implement disposable emulator/browser checks, run them on the relevant
independent stacks, and prepare a reproducible iPhone test checklist. Report
failures and fix them before asking the owner to do hands-on phone testing.
Owner decisions that are prerequisites (release scope, permission for a public
tunnel, and permission to handle a production backup) must still be requested
when reached; this order is not permission to bypass them. Do not start a tunnel
or access production data unattended. After local checks pass, arrange one short
manual iPhone session; then make the release decision. Android physical-device
acceptance remains pending without an Android phone.

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
6. **Manual iPhone acceptance (only if offline ships, after local checks).**
   With the owner's explicit approval, start the chosen candidate locally with
   a **fresh disposable SQLite DB and random test-only secrets** bound to
   loopback, then expose only that disposable server through a short-lived,
   reputable HTTPS tunnel with a stable URL for the duration of the session.
   Agree on the tunnel provider and internet exposure before starting; do not
   expose production data, credentials or an admin session. An owner-approved
   separate test Railway environment is an alternative, not an assumed free
   resource. Avoid publishing credentials in URLs, logs, screenshots or chat.
   On the iPhone, open the HTTPS URL in Safari, sign in to a disposable room,
   add it to the Home Screen, verify the installed app has a saved room and
   meaningful list/item content, then enable airplane mode, force-close and
   reopen the icon to check read-only lists and Last saved (including a list
   not opened online). Check the already-open in-page read-only view, old root
   icon if one exists, reconnect/update, and password revocation or deletion
   from a second session. Confirm old offline content remains readable while
   disconnected and is cleared after a definitive online denial. Record iOS /
   Safari version, URL mode, steps, screenshots with **test data only**, pass /
   fail and limitations; if storage is evicted or the shell cannot load, report
   the failure rather than weakening the gate. Shut down the tunnel/server
   afterward and verify they are no longer reachable. Manual Safari behavior
   does not establish physical Android behavior or Railway proxy correctness.

## Owner decision before any release

- Choose the features/release candidate before combined validation. Arrange
  the iPhone session **after automated/local checks** and explicitly decide
  whether its results are sufficient. If iPhone testing is blocked, installed
  iPhone behavior remains unverified; physical Android behavior remains
  unverified without an Android phone. Do not promise reliable offline shopping
  on untested devices. A release without offline is safer if that gap is
  unacceptable.
- Decide how/when a private production backup can be provided for the schema
  rehearsals, without exposing it to tests, public hosting, or version control.
- Review the deployment checklist and rollback/restore readiness. Only the
  owner may authorize moving `main`, any push, Railway deployment, and the
  timing. Production smoke checks occur **after** an authorized deploy and do
  not count as pre-deploy evidence.

## Progress

- [x] Drafted plan against current documentation and independently rebased stacks.
- [ ] Owner chooses the release scope and accepts or revises the proposed gates.
- [ ] Implement/verify disposable emulator and trusted-HTTPS tests; finish local checks before requesting hands-on iPhone time.
- [ ] Rehearse selected migrations on separate protected production-backup copies, after owner approval.
- [ ] Construct and verify the chosen combined release candidate, if applicable.
- [ ] Owner approves an HTTPS tunnel or separate test deployment; perform and record disposable installed-iPhone checks after local tests pass.
- [ ] Owner makes a separate release decision, including explicit physical Android risk acceptance if offline ships.
