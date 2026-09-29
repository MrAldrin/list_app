# Backlog

Unfinished and deliberately deferred work. Current behavior belongs in
[`ARCHITECTURE.md`](../ARCHITECTURE.md) and linked `docs/` references;
completed-work history is preserved in version control.

## Pending production and device verification

These features are implemented and covered by local automated tests. Local
tests are not production or real-device evidence. Follow the
[deployment checklist](../docs/deployment.md#deployment-checklist) and record
results (with OS/browser versions for devices) in the linked reference.

- [ ] Complete the deployment guide's outstanding production checks: persistence across restart/deployment, migration verification, and remembered room access/password-reset revocation. Earlier repair checks do not establish that the full checklist is complete.
- [ ] Confirm production startup logs show no duplicate-name migration error after deploying the unique item-name index. The 2026-09-28 production backup copy had no duplicates and started cleanly with the index.
- [ ] Verify the checked-item visibility migration on production and its behavior on real devices. See [hiding checked-off items](../docs/checked-item-visibility.md#existing-lists-and-verification).
- [ ] Confirm on Railway that automatic reload is off by default. See [deployment configuration](../docs/deployment.md#configuration).
- [ ] Complete the [public-sharing deployment and device checks](../docs/public-sharing.md#rollout-and-verification).
- [ ] Complete manual multi-user verification for deleted-list handling on real devices or deployment. Local Chromium/Firefox coverage is listed in [browser testing](../docs/browser-testing.md#deleted-list-regression-checks).
- [ ] Complete the real iPhone and Android acceptance checklist in [`docs/home-screen-installation.md`](../docs/home-screen-installation.md): fresh/password-prompt installs, legacy token migration, old icons, multiple rooms, other pages, deleted rooms, restart, and password revocation. Automated cookie-transfer checks do not verify OS installation behavior.

## Security

- [ ] Remove the temporary legacy room-password localStorage cleanup after 2027-09-18; retain token authentication and revocation. See the dated TODO in [`src/main.py`](../src/main.py).

## Data correctness — next priorities

Current quantity and stale-page safeguards are described in
[`docs/item-writes.md`](../docs/item-writes.md).

- [ ] Resolve item-target identity (chunk 5 of the [write atomicity audit](write-atomicity-audit.md)). SQLite can reuse a deleted maximum `items.id` within the same live list. `main.py`'s `toggle_tag`, `toggle`, `change_qty`, `save`, and `delete` callbacks retain an item ID plus list ID/slug; a reproduced stale quick-tag callback changed a newly created replacement item after the old maximum-ID item was deleted. Decide a separate identity/migration approach (for example, a non-reusable ID migration or a stable per-item generation key) before implementation; schema changes are not yet authorized. Add stale-callback regression coverage once the approach is approved. The audit records the verified partial fixes and chunk 6 cross-path regression; do not claim broader database stability from these automated checks.

## Deployment and recovery — next priorities

Configuration, database checks, and recovery instructions live in
[`docs/deployment.md`](../docs/deployment.md).

- [ ] **Your Railway dashboard step:** Open production `list_app` → **Backups** and enable **Weekly** for the `/data` volume; confirm the schedule is listed, then check that a snapshot appears after its first run. The CLI API attempt returned `Not Authorized` and a follow-up query found no schedule; do not assume backups are running. If Weekly is unavailable, check plan/permissions and report back before changing approach. See the [backup options](backup-options.md#weekly-railway-schedule-and-future-home-backup-server).
- [ ] Longer term, set up regular SQLite-consistent off-service backups, retention, restricted access, an owner and failure notification; test restoration with the app stopped, including a hosted restore drill. Weekly Railway volume snapshots alone do not complete this work. See the [backup options](backup-options.md) and [deployment guide](../docs/deployment.md#sqlite-consistent-backups).
- [ ] Later, add a Railway `staging` environment before production pushes. See the [staging environment plan](staging-environment.md).

## Database hardening — planned follow-up

- [ ] Introduce versioned, transaction-safe migrations (for example `PRAGMA user_version`) with rollback on failure and tests for fresh, legacy, missing-foreign-key, already-migrated, and invalid-data databases. Check integrity before committing changes.
- [ ] Evaluate WAL mode and explicitly configure/document SQLite's lock-wait timeout. Python's SQLite connection already has a default timeout; this is not a claim that no timeout exists. Test locking and backup behavior.
- [ ] Strengthen required fields and value constraints deliberately: nullable names, completion state and slugs; quantities below one; length limits; and valid tags JSON. Inspect existing data before enforcing new constraints.

## UI and PWA

- [ ] Follow the [staged frontend/offline migration plan](offline-frontend-migration.md): validate an actual-iPhone prototype, migrate the frontend, then add offline viewing and later editing on the same foundation. Framework selection and implementation require separate approval; the previous experiment is retained as evidence rather than scheduled for integration.

## Testing, documentation, and tooling

- [ ] Resume the [open test-suite speed plan](test-suite-speed.md#resume-here--remaining-work):
  first decide which existing Android scenarios and execution tiers to keep,
  then benchmark the approved checks serially before simplifying them. A small
  real-iPhone acceptance subset and cross-machine desktop browser reliability
  remain unverified. Do not assume extra Android scenarios are approved or add
  offline navigation tests to the current baseline; revisit offline-specific
  device coverage with the future offline feature.
- [ ] Extend regression coverage for tags, room creation/deletion, and the correctness tasks above. Track password-change revocation and public-list authorization tests with their existing security plans.
- [ ] Revisit the Starlette/httpx test-client deprecation when the dependency stack supports its replacement. With installed NiceGUI 3.15.0, Starlette 1.3.1 and httpx 0.28.1, the warning is emitted by `starlette.testclient` imports in tests; no production callsite or dependency upgrade is warranted solely to suppress it.

## Deliberately deferred — revisit when needed

These are not prerequisites for the current small MVP. Revisit when growth, maintenance, or product requirements justify them. Password-length enforcement and CI are low priority; do not schedule them in the near future.

- Enforce a minimum password length in code if password policy becomes a priority.
- Add CI for formatting, lint, and tests when automated change checks become worthwhile. Before adding `.github/`, replace the broad `.*/` ignore rule with explicit runtime-directory rules; keep databases, backups, and secrets out of git.

- Consider an always-on Linux backup server on an old laptop for verified SQLite copies outside Railway, only after testing the simple weekly snapshot schedule; design secure access, disk encryption, power/network reliability, alerts and restore drills first. See the [backup options](backup-options.md#weekly-railway-schedule-and-future-home-backup-server).
- Target realtime refreshes by list/room rather than refreshing unrelated users globally.
- Defer cross-room list pinning until its authorization and UX are designed; see [`plans/advanced_sharing.md`](advanced_sharing.md).
- Split `src/main.py` into smaller route/auth/UI modules and gradually adopt a proper Python package rather than fragile top-level imports.
- Replace the global SQLite connection with a connection/context-manager layer if concurrency or lifecycle complexity requires it.
- Add timestamps and change versions when debugging, conflict detection, or audit history needs them.
- Add individual accounts/invitations only if per-person permissions or revocation are required; shared room access does not establish individual identity.
- Normalize JSON tags only when querying or integrity requirements justify separate tables.
- Reconsider database architecture for multiple replicas, sustained write contention, managed high availability, or multiple regions; discuss any stack change against [`ARCHITECTURE.md`](../ARCHITECTURE.md) first. PostgreSQL, SQLAlchemy/Alembic, and a replacement frontend are not prerequisites for closing this audit.
