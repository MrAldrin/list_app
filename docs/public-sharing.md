# Public list sharing

## Behavior

- **Share** on a list produces `/share/<token>`. Anyone holding it can view and
  edit that list without the room password. It does not grant room management.
- **Reset share link** is visible to authorized room members and asks for
  confirmation. The server rechecks current room authorization and list ownership
  in the same transaction as rotation. An admin login alone is insufficient.
- Resetting invalidates the previous link for everyone. Already-open public
  pages cannot keep editing with it; their next action/refresh or periodic check
  removes access. Previously displayed or copied data cannot be recalled.
- Room navigation continues using `/list/<slug>`, now requiring room access.
  An unauthorized visitor sees a room-entry button, not list contents or a token.
  Old URLs never publicly redirect to a new token. Room access survives rotation.
- Share links are independent of room passwords. Changing a room password revokes
  room authorization, **not public share links**; reset those separately if needed.

## Implementation

`lists.share_token` has a unique index. New lists and legacy lists receive
`secrets.token_urlsafe(32)` tokens (256 random bits), stored in the database.
Renaming lists and restarting the app preserve tokens. Tokens are stored in
plaintext: the database already contains the list contents. Treat URLs, browser
history, server request logs, and backups as sensitive. List pages suppress
outgoing referrers; this does not eliminate all URL leakage.

Public list callbacks carry `share:<token>` as their `expected_slug` identity.
Database mutations check that identity inside their write transaction, so reset
also blocks queued edits and undo. Page refreshes, suggestions, and periodic
checks revalidate access. The internal slug remains the identity for room pages.
The application remains single-instance; see [deployment](deployment.md).

## Rollout and verification

Before deploying, take a SQLite-consistent backup as described in the
[deployment guide](deployment.md). Startup adds/backfills tokens automatically.
Existing room URLs/passwords, manifest addresses, and remembered-access mechanisms
are unchanged. Replace any previously saved/shared public list URLs with new
Share links. Rolling back to older application code re-exposes the old public
slug routes; do not treat that as a security-preserving rollback.

Automated coverage checks legacy migration/restart stability, unique/scoped
lookup, invalid tokens, rename persistence, room authorization for rotation,
old-token rejection across mutations and undo, and page access/control visibility.

**Pending manual deployment checks:**

- Open a room and list using remembered access on the deployed app.
- Share to another browser without room access; verify view and item editing.
- Reset from the room-authorized browser; immediately attempt edits and undo
  in the old public tab, then reload the old link. Verify the new link works.
- Verify unauthorized old slug URLs reveal no contents or new tokens.
- Restart and verify room access and current public links still work.
- Check installed-app launch/navigation on iPhone and Android. These real-device
  checks are not established by automated tests.
