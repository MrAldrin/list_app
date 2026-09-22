# Backlog

Small follow-up ideas that are not currently being implemented.

## Important improvements

- [x] Replace browser-stored room passwords with persistent, revocable room access tokens. Keep bcrypt password hashes in the database, invalidate tokens when a room password changes, and preserve restart/PWA access. See [`ARCHITECTURE.md`](../ARCHITECTURE.md) and [`docs/home-screen-installation.md`](../docs/home-screen-installation.md) for current behavior.
- [ ] Replace guessable public list slugs with separate high-entropy share tokens. Keep public links editable, support token rotation to revoke old links, and retire or restrict the old slug URLs. See [`plans/public_list_share_tokens.md`](public_list_share_tokens.md).

## Security

- [ ] Enforcing minimum password length in code: not implemented.
- [x] Handle malformed or unsupported legacy room password hashes safely: all room password checks reject invalid bcrypt data instead of raising an exception. Regression tests cover verification, login, password changes, deletion, and recovery through an admin password reset. No database migration or automatic hash repair is needed.
- [ ] Remove the temporary legacy room-password localStorage cleanup after 2027-09-18; retain token authentication and revocation. See the dated TODO in [`src/main.py`](../src/main.py).

## Data correctness — next priorities

- [ ] Prevent concurrent duplicate items: add a database uniqueness rule consistent with the app's name normalization and make add/restore atomic (one indivisible operation). Check existing duplicates before adding the constraint; test concurrent requests.
- [x] Make quantity increments/decrements atomic in SQL instead of writing a value calculated from an old UI view. The +/− buttons now apply deltas to the stored quantity, retaining the minimum of one. Regression tests cover concurrent changes, legacy null quantities, list scoping, and stale-list identity protection. Explicit quantity edits in the edit dialog remain unchanged.
- [ ] Preserve all item information when undoing deletion, including description and quantity. Decide whether the original ID must be restored and test duplicate-name conflicts.
- [ ] Complete manual multi-user verification for deleted-list handling: room-authorized deletion shows the specific unavailable message and `Back to room`; public-link users see the generic message without a room button; test immediate add/edit/toggle/quantity/tag/undo actions around deletion and room deletion.
- [x] Protect stale list pages from SQLite ID reuse: validate the original list slug inside the same write transaction before mutations; regression coverage exists.
- [ ] Validate name and quantity together before saving an item edit. An invalid or duplicate name must leave every field unchanged; save valid edits in one transaction.
- [ ] Review other multi-step writes for atomicity, especially list/room deletion and service operations that read, check, then write. Use transactions and a consistent service layer; test rollback on failure.

## Deployment and recovery — next priorities

- [ ] Disable automatic reload in production; retain it only as an explicit development option.
- [ ] Declare `python-dotenv` as a runtime dependency, or make loading `.env` development-only. Do not rely on it arriving through another dependency.
- [ ] Set up regular SQLite-consistent backups, including an off-service copy, retention, and restricted access. Document and test restoration with the app stopped. A code rollback does not reverse a database migration. The one-time repair backup is not a recurring backup policy.
- [ ] Document deployment checks: absolute `DB_PATH` on the persistent volume, one app process/service and no horizontal replicas, persistence across restart, migration verification, and a recovery procedure.
- [ ] Verify remembered room-token access after a real restart/deployment and password reset; complete the device/PWA checklist in [`docs/home-screen-installation.md`](../docs/home-screen-installation.md).

## Database hardening — planned follow-up

- [ ] Introduce versioned, transaction-safe migrations (for example `PRAGMA user_version`) with rollback on failure and tests for fresh, legacy, missing-foreign-key, already-migrated, and invalid-data databases. Check integrity before committing changes.
- [ ] Evaluate WAL mode and explicitly configure/document SQLite's lock-wait timeout. Python's SQLite connection already has a default timeout; this is not a claim that no timeout exists. Test locking and backup behavior.
- [ ] Strengthen required fields and value constraints deliberately: nullable names, completion state and slugs; quantities below one; length limits; and valid tags JSON. Inspect existing data before enforcing new constraints.

## UI and PWA

### Home-screen onboarding — room launch and cookie access implemented

On iPhone, a new home-screen installation does not inherit the browser's
`localStorage`. Older installations launch at `/` and rely on that storage for
both the last room and its access token. This can leave a newly installed app
asking for a room link even after the user created and signed into a room.
The pasted-link and remembered-room recovery fixes do not solve this separate
installation issue.

- [x] **Implement a room-specific launch address first.** Room pages now advertise a credential-free room launch manifest, retaining the existing single ListR identity and password/token authorization. Other pages keep the root manifest. Switching rooms does not deliberately retarget installed icons. Automated tests cover manifest isolation, defaults, escaping, missing/deleted rooms, and fresh-launch password prompts. **Real iPhone and Android installation checks remain outstanding**; existing icons are not assumed to update. See [`docs/home-screen-installation.md`](../docs/home-screen-installation.md).
- [x] **Add secure, HTTP-only cookies for remembered access.** HTTPS uses host-only Secure/HttpOnly/SameSite=Lax cookies with one-year persistence, existing revocable tokens, same-origin write checks, and same-origin Socket.IO handshakes. Legacy localStorage access migrates after cookie confirmation; HTTP/cookie-unavailable fallback remains. `ARCHITECTURE.md` records the adopted model. Automated tests cover cookie transfer simulation, validation, revocation, migration fallback, and forged requests. Apple documents cookie copying starting in iOS/iPadOS 17.2, but **real-device installation checks remain outstanding**.

Both approaches are now implemented. The target is correct-room launch without
another sign-in where installation preserves cookies—not a guarantee. Validate
installation behavior on real devices before treating it as verified.

References: [Apple's installation cookie behavior](https://webkit.org/blog/14787/webkit-features-in-safari-17-2/),
[MDN: manifest start_url](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/start_url).

### Other ideas

- [ ] Decide the intended offline behavior. The current service worker does not provide meaningful offline support. Remove misleading fallback behavior or design a tested cache/offline experience; editable offline lists would also require synchronization.

## Testing, documentation, and tooling

- [ ] Extend regression coverage for tags, room creation/deletion, and the correctness tasks above. Track password-change revocation and public-list authorization tests with their existing security plans.
- [ ] Write a beginner-friendly README and a secret-free `.env.example`. Expand `docs/deployment.md` with backup, recovery, and migration instructions.
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
- Keep SQLite and NiceGUI. PostgreSQL, SQLAlchemy/Alembic, and a replacement frontend are not required just to close this audit. Reconsider database architecture for multiple replicas, sustained write contention, managed high availability, or multiple regions; discuss any stack change against `ARCHITECTURE.md` first.

## Resolved or already verified

- [x] Make the default database path independent of the startup directory by resolving `list.db` relative to the project root, while retaining `DB_PATH` as an override for deployments such as Railway. Regression coverage verifies startup from a different working directory.
- [x] Repair item foreign keys locally and on Railway, enable enforcement on the app connection, and add migration tests. Production verification passed: `items → lists`, no foreign-key errors, integrity `ok`, 280 items retained, and add/edit/delete smoke tests passed. The downloaded production backup was also migrated on a separate copy with all fields preserved.
- [x] Confirm Railway uses `DB_PATH=/data/list.db` on the `/data` persistent volume; local development uses a project-relative default path.
- [x] Production password configuration is documented as randomly generated and stored in Bitwarden. The audit's local short-password observation is not evidence of a weak production password; minimum-length policy remains above.
- [x] Make password configuration fail closed: require nonblank `APP_PASSWORD` for local and hosted startup before opening the database, remove the default-room fallback password, and always require admin authentication. Regression tests cover invalid configuration, valid startup, and preserving existing room passwords.

## Local-only cleanup / verification

- [ ] If retaining the disposable local test database, check whether the audit's malformed test-room password hash remains and repair or remove that test fixture if useful. No production corruption is inferred from that old local finding. The general malformed-hash handling task remains in Security.

## Tracking

- Home-screen onboarding: room-specific launch and cookie-backed access implemented with automated coverage; real-device installation checks pending.
- Existing security plans remain linked above; planned work is not claimed to be implemented.
- 2026-09-15: Reconciled the remaining codebase audit into this backlog, recorded verified fixes and explicit deferrals, and retired `agent_files/codebase-audit.md`. The original assessment remains in version-control history.
- 2026-09-18: Resolved the local default database-path issue; Railway continues to use its explicit `/data/list.db` override.
