# Plan: Persistent and Revocable Room Access Tokens

## Status

Not implemented. This plan addresses audit item 5.

Created: 2026-09-14

## Goal

Stop storing room passwords in browser `localStorage` while keeping the behaviour that users care about:

- A user enters a room password once per browser/device.
- The room remains available after app restarts and deployments.
- The PWA home-screen shortcut continues opening the user's room.
- Resetting a room password revokes existing users' access.

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

1. Generate a cryptographically random, opaque token.
2. Store only a hash of the token in the database.
3. Associate the token with its room and current authorization version.
4. Store the raw token in browser `localStorage` under a new token key, for example `listapp_room_token_{slug}`.

The raw token is a bearer credential, but it cannot reveal the room password and can be revoked independently.

Suggested database structure:

- Add an authorization version to `rooms`, initially `1`.
- Add a `room_access_tokens` table containing a token hash, room ID, authorization version, creation time, and optional revocation time.
- Add foreign keys and indexes as part of the database migration.

### 3. Validate tokens on room access

The server must validate the token and its authorization version before granting private room access. `authorized_rooms` may remain as a convenience/cache for navigation, but it must not be the only authorization check.

If a token is invalid or revoked:

- Remove the token from browser storage.
- Remove the room from the remembered authorization state.
- Show the room password prompt.

Public list URLs remain public, as defined by `ARCHITECTURE.md`.

### 4. Revoke access when a password changes

All room-password-changing paths must use the same operation:

1. Replace the bcrypt password hash.
2. Increase the room authorization version.
3. Revoke or invalidate all older room tokens.

Users with an old token must enter the new password and receive a new token. A currently open page may notice this on its next server-side authorization check; immediate redirection of every open client would require an additional broadcast feature.

## Rollout plan: one-time login for existing users

This uses the agreed simple rollout rather than a silent migration:

1. Deploy token authentication.
2. Stop accepting the old `listapp_room_{slug}` password values as authorization.
3. Temporarily remove legacy room-password keys from browser `localStorage`.
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

## Suggested implementation order

1. Add the schema migration for room authorization versions and access tokens.
2. Add database/service functions to issue, validate, and revoke tokens.
3. Add tests for token lifecycle and authorization-version invalidation.
4. Replace room-page and root-route password reuse with token validation.
5. Update password changes and admin resets to revoke tokens.
6. Add the temporary legacy-password cleanup and its dated removal TODO.
7. Test normal navigation, restart recovery, deployment recovery, password reset, and PWA home-screen behaviour.
8. Remove the temporary cleanup after the one-year window.

## Tests and acceptance criteria

- Room passwords remain bcrypt hashes and are never written to localStorage by the new flow.
- A valid token grants access to only its associated room.
- Invalid, expired, revoked, or wrong-room tokens require the password again.
- Resetting a room password invalidates all previous tokens.
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

- [ ] Database schema and migration
- [ ] Token issue/validation/revocation service
- [ ] Room and root-route integration
- [ ] Password-reset invalidation
- [ ] One-time legacy-password cleanup
- [ ] Automated tests
- [ ] Manual restart, deployment, and PWA verification
- [ ] Remove temporary cleanup after one year
