# Backlog

Unfinished and deliberately deferred work. Current behavior belongs in
[`ARCHITECTURE.md`](../ARCHITECTURE.md) and linked `docs/` references;
completed-work history is preserved in version control.

## Important improvements

- [ ] Replace guessable public list slugs with separate high-entropy share tokens. Keep public links editable, support token rotation to revoke old links, and retire or restrict the old slug URLs. See [`plans/public_list_share_tokens.md`](public_list_share_tokens.md).

## Security

- [ ] Enforce a minimum password length in code.
- [ ] Remove the temporary legacy room-password localStorage cleanup after 2027-09-18; retain token authentication and revocation. See the dated TODO in [`src/main.py`](../src/main.py).

## Data correctness — next priorities

Current quantity and stale-page safeguards are described in
[`docs/item-writes.md`](../docs/item-writes.md).

- [ ] Prevent concurrent duplicate items: add a database uniqueness rule consistent with the app's name normalization and make add/restore atomic (one indivisible operation). Check existing duplicates before adding the constraint; test concurrent requests.
- [ ] Preserve all item information when undoing deletion, including description and quantity. Decide whether the original ID must be restored and test duplicate-name conflicts.
- [ ] Complete manual multi-user verification for deleted-list handling: room-authorized deletion shows the specific unavailable message and `Back to room`; public-link users see the generic message without a room button; test immediate add/edit/toggle/quantity/tag/undo actions around deletion and room deletion.
- [ ] Validate name and quantity together before saving an item edit. An invalid or duplicate name must leave every field unchanged; save valid edits in one transaction.
- [ ] Review other multi-step writes for atomicity, especially list/room deletion and service operations that read, check, then write. Use transactions and a consistent service layer; test rollback on failure.

## Deployment and recovery — next priorities

Configuration, database checks, and recovery instructions live in
[`docs/deployment.md`](../docs/deployment.md).

- [ ] Disable automatic reload in production; retain it only as an explicit development option.
- [ ] Declare `python-dotenv` as a runtime dependency, or make loading `.env` development-only. Do not rely on it arriving through another dependency.
- [ ] Set up regular SQLite-consistent backups, including an off-service copy, retention, and restricted access; choose an owner and failure notification. Test restoration with the app stopped, including a hosted restore drill. See the proposed policy in the deployment guide.
- [ ] Complete and record the deployment guide's outstanding production checks, including persistence across restart/deployment, migration verification, and remembered room access/password-reset revocation. Earlier repair checks do not establish that the full checklist is complete.

## Database hardening — planned follow-up

- [ ] Introduce versioned, transaction-safe migrations (for example `PRAGMA user_version`) with rollback on failure and tests for fresh, legacy, missing-foreign-key, already-migrated, and invalid-data databases. Check integrity before committing changes.
- [ ] Evaluate WAL mode and explicitly configure/document SQLite's lock-wait timeout. Python's SQLite connection already has a default timeout; this is not a claim that no timeout exists. Test locking and backup behavior.
- [ ] Strengthen required fields and value constraints deliberately: nullable names, completion state and slugs; quantities below one; length limits; and valid tags JSON. Inspect existing data before enforcing new constraints.

## UI and PWA

- [ ] Complete the real iPhone and Android acceptance checklist in [`docs/home-screen-installation.md`](../docs/home-screen-installation.md): fresh/password-prompt installs, legacy token migration, old icons, multiple rooms, other pages, deleted rooms, restart, and password revocation. Record OS/browser versions and results; automated cookie-transfer checks do not verify OS installation behavior.
- [ ] Decide the intended offline behavior. The current service worker does not provide meaningful offline support. Remove misleading fallback behavior or design a tested cache/offline experience; editable offline lists would also require synchronization.

## Testing, documentation, and tooling

- [ ] Extend regression coverage for tags, room creation/deletion, and the correctness tasks above. Track password-change revocation and public-list authorization tests with their existing security plans.
- [ ] Add CI for formatting, lint, and tests. Replace the broad `.*/` ignore rule with explicit runtime-directory rules so directories such as `.github/` can be tracked. Keep databases, backups, and secrets out of git.
- [ ] Recheck the audit's `lastrowid` possibly being `None` type-check warning and address it if still present. Review the Starlette/httpx deprecation warning separately; avoid blind dependency upgrades.

## Deliberately deferred — revisit when needed

These are not prerequisites for the current small MVP. Revisit when growth, maintenance, or product requirements justify them.

- Target realtime refreshes by list/room rather than refreshing unrelated users globally.
- Defer cross-room list pinning until its authorization and UX are designed; see [`plans/advanced_sharing.md`](advanced_sharing.md).
- Split `src/main.py` into smaller route/auth/UI modules and gradually adopt a proper Python package rather than fragile top-level imports.
- Replace the global SQLite connection with a connection/context-manager layer if concurrency or lifecycle complexity requires it.
- Add timestamps and change versions when debugging, conflict detection, or audit history needs them.
- Add individual accounts/invitations only if per-person permissions or revocation are required; shared room access does not establish individual identity.
- Normalize JSON tags only when querying or integrity requirements justify separate tables.
- Reconsider database architecture for multiple replicas, sustained write contention, managed high availability, or multiple regions; discuss any stack change against [`ARCHITECTURE.md`](../ARCHITECTURE.md) first. PostgreSQL, SQLAlchemy/Alembic, and a replacement frontend are not prerequisites for closing this audit.

## Local-only cleanup / verification

- [ ] If retaining the disposable local test database, check whether the audit's malformed test-room password hash remains and repair or remove that test fixture if useful. No production corruption is inferred from that old local finding. Safe rejection of malformed hashes is already implemented; see [`docs/home-screen-installation.md`](../docs/home-screen-installation.md#room-authorization-and-token-persistence).
