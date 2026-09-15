# Backlog

Small follow-up ideas that are not currently being implemented.

## Important improvements

- [ ] Make the default database path independent of the startup directory by resolving `list.db` relative to the project root, while retaining `DB_PATH` as an override for deployments such as Railway. Add a test for starting from a different working directory.
- [ ] Make password configuration fail closed. If `APP_PASSWORD` is missing, the app currently leaves `/admin` unprotected and may create the default room with the known `dev_password`. Best solution: require `APP_PASSWORD` in production and remove the fallback; use an explicit, development-only setting locally. Railway already provides `APP_PASSWORD`, but fail-closed behavior protects against deployment misconfiguration.
- [ ] Replace browser-stored room passwords with persistent, revocable room access tokens. Keep bcrypt password hashes in the database, invalidate tokens when a room password changes, and preserve restart/PWA access. Use the one-time rollout and temporary legacy-password cleanup described in [`plans/room_access_tokens.md`](room_access_tokens.md).
- [ ] Replace guessable public list slugs with separate high-entropy share tokens. Keep public links editable, support token rotation to revoke old links, and retire or restrict the old slug URLs. See [`plans/public_list_share_tokens.md`](public_list_share_tokens.md).

## Security

- [ ] Enforcing minimum password length in code: not implemented.
- [ ] Handle malformed or legacy room password hashes safely: `verify_room()` should treat invalid bcrypt data as a failed login instead of raising an exception, with a regression test.

## Data correctness — next priorities

- [ ] Prevent concurrent duplicate items: add a database uniqueness rule consistent with the app's name normalization and make add/restore atomic (one indivisible operation). Check existing duplicates before adding the constraint; test concurrent requests.
- [ ] Make quantity increments/decrements atomic in SQL instead of writing a value calculated from an old UI view. Retain the minimum quantity of one and test concurrent changes.
- [ ] Preserve all item information when undoing deletion, including description and quantity. Decide whether the original ID must be restored and test duplicate-name conflicts.
- [ ] Validate name and quantity together before saving an item edit. An invalid or duplicate name must leave every field unchanged; save valid edits in one transaction.
- [ ] Review other multi-step writes for atomicity, especially list/room deletion and service operations that read, check, then write. Use transactions and a consistent service layer; test rollback on failure.

## Deployment and recovery — next priorities

- [ ] Disable automatic reload in production; retain it only as an explicit development option.
- [ ] Declare `python-dotenv` as a runtime dependency, or make loading `.env` development-only. Do not rely on it arriving through another dependency.
- [ ] Set up regular SQLite-consistent backups, including an off-service copy, retention, and restricted access. Document and test restoration with the app stopped. A code rollback does not reverse a database migration. The one-time repair backup is not a recurring backup policy.
- [ ] Document deployment checks: absolute `DB_PATH` on the persistent volume, one app process/service and no horizontal replicas, persistence across restart, migration verification, and a recovery procedure.

## Database hardening — planned follow-up

- [ ] Introduce versioned, transaction-safe migrations (for example `PRAGMA user_version`) with rollback on failure and tests for fresh, legacy, missing-foreign-key, already-migrated, and invalid-data databases. Check integrity before committing changes.
- [ ] Evaluate WAL mode and explicitly configure/document SQLite's lock-wait timeout. Python's SQLite connection already has a default timeout; this is not a claim that no timeout exists. Test locking and backup behavior.
- [ ] Strengthen required fields and value constraints deliberately: nullable names, completion state and slugs; quantities below one; length limits; and valid tags JSON. Inspect existing data before enforcing new constraints.

## UI and PWA

- [ ] Allow user zoom by removing restrictive viewport settings; retain suitable input font sizes to avoid unwanted iOS input zoom.
- [ ] Decide the intended offline behavior. The current service worker does not provide meaningful offline support. Remove misleading fallback behavior or design a tested cache/offline experience; editable offline lists would also require synchronization.

## Testing, documentation, and tooling

- [ ] Extend regression coverage for tags, room creation/deletion, and the correctness tasks above. Track password-change revocation and public-list authorization tests with their existing security plans.
- [ ] Write a beginner-friendly README and a secret-free `.env.example`. Expand `docs/deployment.md` with backup, recovery, and migration instructions.
- [ ] Add CI for formatting, lint, and tests. Replace the broad `.*/` ignore rule with explicit runtime-directory rules so directories such as `.github/` can be tracked. Keep databases, backups, and secrets out of git.
- [ ] Recheck the audit's `lastrowid` possibly being `None` type-check warning and address it if still present. Review the Starlette/httpx deprecation warning separately; avoid blind dependency upgrades.

## Deliberately deferred — revisit when needed

These are not prerequisites for the current small MVP. Revisit when growth, maintenance, or product requirements justify them.

- Target realtime refreshes by list/room rather than refreshing unrelated users globally.
- Split `src/main.py` into smaller route/auth/UI modules and gradually adopt a proper Python package rather than fragile top-level imports.
- Replace the global SQLite connection with a connection/context-manager layer if concurrency or lifecycle complexity requires it.
- Add timestamps and change versions when debugging, conflict detection, or audit history needs them.
- Add individual accounts/invitations only if per-person permissions or revocation are required; shared room access does not establish individual identity.
- Normalize JSON tags only when querying or integrity requirements justify separate tables.
- Keep SQLite and NiceGUI. PostgreSQL, SQLAlchemy/Alembic, and a replacement frontend are not required just to close this audit. Reconsider database architecture for multiple replicas, sustained write contention, managed high availability, or multiple regions; discuss any stack change against `ARCHITECTURE.md` first.

## Resolved or already verified

- [x] Repair item foreign keys locally and on Railway, enable enforcement on the app connection, and add migration tests. Production verification passed: `items → lists`, no foreign-key errors, integrity `ok`, 280 items retained, and add/edit/delete smoke tests passed. The downloaded production backup was also migrated on a separate copy with all fields preserved.
- [x] Confirm Railway uses `DB_PATH=/data/list.db` on the `/data` persistent volume. The separate local relative-path concern remains above.
- [x] Production password configuration is documented as randomly generated and stored in Bitwarden. The audit's local short-password observation is not evidence of a weak production password; fail-closed behavior and minimum-length policy remain above.

## Local-only cleanup / verification

- [ ] If retaining the disposable local test database, check whether the audit's malformed test-room password hash remains and repair or remove that test fixture if useful. No production corruption is inferred from that old local finding. The general malformed-hash handling task remains in Security.

## Tracking

- Existing security plans remain linked above; planned work is not claimed to be implemented.
- 2026-09-15: Reconciled the remaining codebase audit into this backlog, recorded verified fixes and explicit deferrals, and retired `agent_files/codebase-audit.md`. The original assessment remains in version-control history.
