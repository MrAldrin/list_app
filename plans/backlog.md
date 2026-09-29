# Backlog

Unfinished and deferred work, sorted by commitment. Details live in the linked
plans and docs. How to add and order items is in
[`AGENTS.md`](../AGENTS.md#documentation-lifecycle).

Tags: `bug`, `feature`, `infra`, `data`, `security`, `refactor`, `docs`, `test`.

## Next

In order: the top item is done first.

- [ ] [data] (in progress) Add versioned, all-or-nothing migrations with integrity checks and a pre-migration backup on the volume. Implemented on bookmark `versioned-migrations`; deploy in the next window with the [deploy runbook](versioned-migrations.md#deploy-runbook-step-5).
- [ ] [bug] Resolve item-target identity: SQLite can reuse a deleted item ID, so stale item actions can change a replacement item. Likely fix: non-reusable IDs via a table rebuild, using the new migrations. See [write atomicity audit](write-atomicity-audit.md) chunk 5 and [findings](../docs/background/write-atomicity-findings.md).

## Later

Agreed as worth doing; no date.

- [ ] [infra] Scheduled local backup job that pulls a verified SQLite copy from Railway to this machine or an always-on home machine. Include a restore drill on a hosted copy. Blocker: Railway snapshots are not available on the current plan. See [backup options](backup-options.md#scheduled-local-copy-railway-snapshots-blocked).
- [ ] [infra] Add a Railway `staging` environment before production pushes. See the [staging environment plan](staging-environment.md).
- [ ] [data] Evaluate WAL mode and explicitly set and document SQLite's lock-wait timeout. Test locking and backup behavior.
- [ ] [data] Strengthen field constraints: nullable names, completion state and slugs; quantities below one; length limits; valid tags JSON. Inspect existing data first.
- [ ] [feature] Follow the [frontend/offline migration plan](offline-frontend-migration.md): iPhone prototype, frontend migration, then offline viewing and editing. Framework choice needs separate approval.
- [ ] [security] After 2027-09-18, remove the temporary legacy room-password localStorage cleanup. Keep token authentication and revocation. See the dated TODO in [`src/main.py`](../src/main.py).
- [ ] [test] Resume the [test-suite speed plan](test-suite-speed.md#resume-here--remaining-work): decide which Android scenarios and tiers to keep, then benchmark before simplifying.
- [ ] [test] Add regression tests for tags and room creation/deletion.

## Ideas

No promise. Revisit when growth, maintenance or product needs justify them. Delete freely.

- [security] Enforce a minimum password length in code.
- [infra] Add CI for format, lint and tests. First replace the broad `.*/` ignore rule with explicit runtime-directory rules; keep databases, backups and secrets out of git.
- [feature] Target realtime refreshes by list/room instead of refreshing all users.
- [feature] Cross-room list pinning, once authorization and UX are designed. See [advanced sharing](advanced_sharing.md).
- [feature] Individual accounts/invitations, only if per-person permissions or revocation are needed.
- [refactor] Split `src/main.py` into route/auth/UI modules and move to a proper Python package.
- [refactor] Replace the global SQLite connection with a connection/context-manager layer.
- [data] Add timestamps and change versions for debugging, conflict detection or audit history.
- [data] Normalize JSON tags into tables if querying or integrity needs it.
- [data] Reconsider the database for multiple replicas, heavy write contention, high availability or multiple regions. Discuss against [`ARCHITECTURE.md`](../ARCHITECTURE.md) first.

## Manual checks

For the owner to do when convenient. Local tests are not production or
real-device evidence. Follow the
[deployment checklist](../docs/deployment.md#deployment-checklist) and record
results (with OS/browser versions for devices) in the linked doc.

- [ ] Finish the deployment guide's outstanding production checks: persistence across restart/deployment, migration verification, remembered room access and password-reset revocation.
- [ ] Confirm production startup logs show no duplicate-name migration error after deploying the unique item-name index.
- [ ] Verify the [checked-item visibility](../docs/checked-item-visibility.md#existing-lists-and-verification) migration on production and real devices.
- [ ] Confirm on Railway that automatic reload is off by default. See [deployment configuration](../docs/deployment.md#configuration).
- [ ] Do the [public-sharing deployment and device checks](../docs/public-sharing.md#rollout-and-verification).
- [ ] Verify deleted-list handling with multiple users on real devices or production. Local coverage is in [browser testing](../docs/browser-testing.md#deleted-list-regression-checks).
- [ ] Run the real iPhone and Android checklist in [home-screen installation](../docs/home-screen-installation.md).
