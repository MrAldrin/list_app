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

## Tracking

- Added during the codebase audit discussion.
