# Self-service room creation

1. Sign in at `/admin`.
2. Under **Room invitations**, select **Generate 7-day invitation**.
3. Copy and save the displayed link; the full link is shown only once.
4. Share it with your group. Each person can choose a room name and password, then sign into their new room. They should keep the room URL and password.
5. Use **Revoke** beside an active invitation to stop further room creation immediately.

An invitation is reusable until seven days after generation (creation and expiry times are displayed in UTC). If you lose the link, revoke it and generate another. Existing rooms work normally after expiry/revocation. Admin sees newly created rooms in the usual overview; reload if another person has just created one.

Anyone receiving or being forwarded an invitation can create a room. The invitation does not grant access to existing rooms. Room passwords grant management rights to everyone holding them; individual list URLs remain public-by-link. Admin login alone does not grant room access: admins must also use the room password or a valid room-access token. Admins can still view the room overview and reset room passwords, so this is not privacy from the server administrator.

## Invitation history

Revoked and expired invitations remain visible for seven days after they first become inactive (revocation or expiry, whichever happens first). Opening or refreshing the admin invitation list automatically deletes older invitation records. There is no background scheduler, so records may stay in the database longer if nobody opens the admin page. Deleted invitation links remain invalid; existing rooms and their access tokens are unaffected. No additional database migration is needed for this cleanup.

## Implementation boundaries

`src/room_invitations.py` stores invitation token hashes and lifecycle timestamps
in the separate `room_invitations` table. Public creation at
`/create-room/{token}` rechecks expiry and revocation inside the room-creation
transaction, so an earlier valid page load is not enough to authorize creation.
`src/ui/room_invitations.py` rechecks admin authentication in invitation-management
callbacks. Creators choose a room password and then use the normal room sign-in
flow; invitations do not introduce individual accounts. No rate limiting or
CAPTCHA is implemented for this feature.

## Deployment and migration

Normal startup adds `room_invitations` if missing; no manual SQL is needed. Existing room/list rows do not need to be rewritten for this feature. The original local database was not used for destructive testing. Migration was tested twice on a temporary SQLite backup copy, with existing rows compared and integrity/foreign-key checks run.

There is no automated backup system or abuse throttling in this feature, by agreement. Production should use HTTPS. Invitation pages send `Cache-Control: no-store` and `Referrer-Policy: no-referrer`, but links still appear in browser history and may appear in hosting access logs. Treat those logs as private. Only the token hash is stored in the application database.

Future personal accounts can replace room-password authorization independently of creation invitations.
