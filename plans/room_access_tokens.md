# Plan: Persistent and Revocable Room Access Tokens

## Status

Implemented. Manual restart, deployment, and PWA verification remain. This plan addresses audit item 5.

Created: 2026-09-14

## Goal

Stop storing room passwords in browser `localStorage` while keeping the behaviour that users care about:

- A user enters a room password once per browser/device.
- The room remains available after app restarts and deployments.
- The PWA home-screen shortcut continues opening the user's room.
- Resetting a room password revokes existing users' private room access. Previously shared public list links remain usable.

## Implementation proposal

Implement this in small, testable stages without changing the NiceGUI/SQLite architecture:

1. **Schema:** add a room authorization version and a `room_access_tokens` table. Run the migration transactionally and preserve all existing room passwords.
2. **Token service:** add functions to generate a secure random token, hash it for storage, validate it for the correct room/version, and revoke it.
3. **Authentication integration:** after a successful password login, store the raw token in browser `localStorage`. On room and root-route access, read and validate the token server-side. Treat `authorized_rooms` only as a navigation cache.
4. **Revocation:** make password changes, admin resets, and room deletion invalidate tokens. Use one shared database operation for password changes and authorization-version updates.
5. **Legacy cleanup:** stop accepting `listapp_room_*` password values, remove them during a one-time rollout, and keep `listapp_last_room` so PWA/restart routing still works.
6. **Verification:** add lifecycle/security tests first, then test restart recovery, password reset, multiple browsers, and PWA home-screen navigation manually.

## Current behaviour

- `rooms.password_hash` stores a bcrypt hash. This must remain; it is not plain text.
- After login, the actual room password is stored in browser `localStorage` under `listapp_room_{slug}`.
- `app.storage.user` stores `authorized_rooms` and the last room, but the current code trusts an authorized slug without checking that the authorization is still valid.
- The root route and `listapp_last_room` provide the PWA restart/home-screen experience.

## Chosen design

### 1. Keep room password hashes

Continue storing the bcrypt password hash in `rooms.password_hash`. Password entry is still needed when a new token must be issued, and password resets still replace this hash.

Do not store or write the plain password after the new flow is deployed.

### 2. Add persistent room access tokens

After a successful password check:

1. Generate a cryptographically random, opaque token using 32 random bytes (for example, `secrets.token_urlsafe(32)`).
2. Store only its SHA-256 hash in the database. Random tokens do not need bcrypt; room passwords still do.
3. Associate the token with its room and current authorization version.
4. Store the raw token in browser `localStorage` under a new token key, for example `listapp_room_token_{slug}`.

The raw token is a bearer credential, but it cannot reveal the room password and can be revoked independently.

Suggested database structure:

- Add an authorization version to `rooms`, initially `1`.
- Add a `room_access_tokens` table containing a token hash, room ID, authorization version, creation time, and optional revocation time.
- Add a unique index on the token hash and an index on room ID.
- Enable SQLite foreign-key enforcement and cascade token deletion when its room is deleted.
- Tokens do not expire automatically in this MVP. They remain valid until individually revoked, their room password changes, or their room is deleted.
- Reuse valid tokens rather than issuing a new token on every visit. Remove obsolete token rows during password resets to avoid unnecessary accumulation.
- The migration must preserve existing rooms, lists, and password hashes and be safe to run again.

### 3. Validate tokens on room access

The server must validate the token and its authorization version before granting private room access. `authorized_rooms` may remain as a convenience/cache for navigation, but it must not be the only authorization check.

If a token is invalid or revoked:

- Remove the token from browser storage.
- Remove the room from the remembered authorization state.
- Show the room password prompt.

Validate authorization on every private room operation, not only when rendering a page. This includes callbacks from already-open pages, such as room renaming and list creation, and any private refresh/read paths. Use a shared server-side authorization helper rather than scattered checks. Bind authorization to the target room; never trust a room ID supplied by the browser on its own.

An authenticated administrator may access rooms through an explicit admin authorization path. An entry in `authorized_rooms` alone must never grant access, including entries created by old admin flows. Normal room password changes and deletion retain their existing password-confirmation requirements; admin resets use the admin authorization path.

Only erase a token when the server has conclusively found it invalid. Browser-storage timeouts and database failures must fail closed (no private access), preserve stored credentials, and offer retry. If browser storage cannot be written, explain that access cannot be remembered on that device.

Public list URLs remain public, as defined by `ARCHITECTURE.md`.

### 4. Revoke access when a password changes

All room-password-changing paths must use the same operation:

1. Replace the bcrypt password hash.
2. Increase the room authorization version.
3. Revoke or invalidate all older room tokens.

The password-hash update and authorization-version increment must happen in one database transaction. Token issuance must also guard against a concurrent password reset: a password verified against an older version must never issue a token under the newer version. Keep authorization checks and private mutations transactionally consistent so a reset cannot slip between the check and the write.

After a normal password change, issue a fresh token to the device that changed it; all other devices must enter the new password. An admin reset does not automatically authorize other devices.

A currently open page must be denied its next private operation after revocation. Immediate visual redirection is optional; immediate enforcement on subsequent private operations is required. Already displayed information cannot be taken back.

## Rollout plan: one-time login for existing users

This uses the agreed simple rollout rather than a silent migration:

1. Deploy token authentication.
2. Stop accepting the old `listapp_room_{slug}` password values as authorization.
3. Temporarily remove legacy room-password keys from browser `localStorage`. Explicitly exclude `listapp_room_token_*`: those new keys share the legacy `listapp_room_` prefix. Run cleanup even when login is needed, and never copy legacy passwords into the new flow.
4. Keep `listapp_last_room` so the root route can still find the user's room.
5. Each existing browser/device enters the room password once.
6. Store the new token and use it for future visits.

The cleanup is temporary. Add a code TODO recording the actual implementation date and a removal date one year later. After that date, remove only the legacy-password cleanup; retain token authentication and token revocation.

A browser/device that never opens the app during the cleanup period may retain its old localStorage value. This is the reason for the one-year window.

## PWA and restart requirements

The implementation must not:

- change the manifest `start_url` from `/`;
- change the manifest `scope` from `/`;
- remove the root route's remembered-room routing;
- clear `listapp_last_room` during credential cleanup;
- require a password merely because the server restarted;
- regenerate `NICEGUI_STORAGE_SECRET` during normal deployments.

The token must be stored in the browser and its hash must be stored in the persistent application database. This allows authorization to recover even if NiceGUI's server-side user storage is lost during a restart.

## Security and scope

- Tokens in localStorage are still bearer credentials accessible to JavaScript. This protects the room password itself but does not prevent script injection from stealing access. HTTP-only cookies remain a possible future improvement.
- Use HTTPS in production. Never put passwords or raw tokens in URLs, logs, or exception messages.
- Encode browser-storage keys and values safely when generating JavaScript (for example, with `json.dumps`); do not interpolate unescaped route slugs.
- No device-management UI, automatic expiry, or real-time forced logout is required for this MVP.
- Update `ARCHITECTURE.md` during implementation: its current room-security rule explicitly describes storing passwords in localStorage and must instead describe revocable tokens and server-side checks.

## Suggested implementation order

1. Add the schema migration for room authorization versions and access tokens.
2. Add database/service functions to issue, validate, and revoke tokens.
3. Add tests for token lifecycle and authorization-version invalidation.
4. Replace room-page and root-route password reuse with token validation, including explicit admin access and guards on private callbacks/read paths.
5. Update password changes and admin resets to atomically revoke tokens; handle concurrent token issuance and refresh the changing device's token.
6. Add the temporary legacy-password cleanup and its dated removal TODO.
7. Update `ARCHITECTURE.md` and test normal navigation, restart recovery, deployment recovery, password reset, and PWA home-screen behaviour. Run the repository's required Python formatting, lint, and test checks.
8. Remove the temporary cleanup after the one-year window.

## Risks and mitigations

- **Migration failure or data loss:** use a transaction, make the migration repeatable, and test it against fresh and existing databases before deployment.
- **PWA/restart regressions:** do not change the manifest, root route, remembered-room key, or storage secret. Test a real restart and home-screen launch.
- **Token theft:** a token remains a bearer credential in `localStorage`, but it cannot reveal the room password and can be revoked. Never put tokens in URLs or logs; store only hashes in SQLite.
- **Stale open pages:** validate authorization on room entry and relevant server-side actions. Immediate notification of every open client is deferred.
- **User disruption:** existing browsers will need one password entry after rollout; preserve the last-room value and explain this in release notes.

## Tests and acceptance criteria

- Room passwords remain bcrypt hashes and are never written to localStorage by the new flow.
- A valid token grants access to only its associated room.
- Invalid, revoked, or wrong-room tokens require the password again; MVP tokens have no automatic expiry.
- Resetting a room password invalidates all previous tokens, including authorization cached in server-side user storage.
- An already-open room cannot perform private operations after another device resets its password.
- Concurrent reset/login cannot turn an old password into a currently valid token; reset and private mutations respect transaction boundaries.
- The device performing a normal password change receives a new token; other devices must log in again.
- Authenticated admin access works explicitly; an old `authorized_rooms` entry alone grants nothing.
- Legacy cleanup removes only old password keys, preserves token keys and `listapp_last_room`, and is safe to repeat.
- Storage/database failures deny private access without deleting valid credentials; failed persistence gives useful feedback.
- Migration preserves existing data and can run repeatedly; deleting a room also deletes its tokens.
- Existing users need to enter a password once per browser/device after rollout, not after every restart.
- A server restart does not require a password when the token and database remain available.
- The root route still returns users to their last room.
- The PWA remains installed and stays in standalone mode.
- Public list links continue to work according to the existing architecture.

## Alternatives not chosen

- Requiring a password after every restart: rejected because it recreates the main usability problem.
- Keeping the password in localStorage and adding only an authorization version: simpler, but it leaves the plain-text browser-storage risk.
- An HTTP-only cookie instead of localStorage: potentially safer against JavaScript access, but more invasive and not needed for the first implementation.

## Progress tracking

- [x] Database schema and migration
- [x] Token issue/validation/revocation service
- [x] Room and root-route integration, explicit admin access, and private-operation guards
- [x] Password-reset invalidation
- [x] One-time legacy-password cleanup
- [x] Architecture documentation update
- [x] Automated tests, including open-page revocation and concurrent reset/login
- [ ] Manual restart, deployment, and PWA verification
- [ ] Remove temporary cleanup after one year
