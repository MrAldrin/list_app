# Plan: Secure Public List Share Tokens

## Status

Not implemented. This plan addresses audit item 6.

Created: 2026-09-14

## Goal

Make public list links difficult to guess while preserving the current product behavior:

- Anyone with a valid list link can open and edit that list.
- Room members can continue opening lists from their room.
- PWA home-screen and restart behavior remain unchanged.
- A list owner/admin can revoke all existing public links by rotating the token.

This improves protection against guessed URLs. It does not make a list private: anyone who receives or discovers a valid link can still use it.

## Current problem

A public URL currently uses the list name and a six-character hexadecimal suffix, for example:

```text
/list/groceries-a1b2c3
```

The suffix has only about 24 bits of randomness (roughly 16.7 million possibilities). If an attacker knows or guesses the list name, they can try suffixes and distinguish a valid list from a missing list.

## Chosen design: separate share token

### Data model

- Keep `lists.slug` for the existing human-readable/internal list identity where useful.
- Add a unique `share_token` to each list, or a separate token table if token history is needed later.
- Generate tokens with a cryptographically secure generator, such as `secrets.token_urlsafe(32)`. This provides 256 bits of randomness; 128 bits would also be sufficient.
- Generate a token when a list is created and backfill tokens for existing lists during migration.
- For the first implementation, storing the random token in the database is acceptable because the database already contains the list data and the token is not a password. If database-compromise protection becomes important, store a token hash and add a separate token-delivery/recovery design.

The list password and share token have different jobs:

- A room password grants access to a room.
- A share token grants access to one public list.

### URL and lookup

Use the token—not the list name—as the public access key. The clearest canonical route is:

```text
/share/<token>
```

A friendly alternative is:

```text
/list/<human-readable-name>/<token>
```

The server must look up the list by token and treat the name portion as display-only. Putting the token after a dash instead of in its own URL segment is equally secure; separate segments are simply clearer and easier to maintain.

The existing public-list behavior remains: a valid token is enough to view and edit the list. No room password is required for a public share link.

### Revocation

To revoke all public access through the current link:

1. Generate a new random token.
2. Replace the list's old token.
3. The old URL no longer matches and stops working.
4. Anyone who still needs access receives the new link.

Users with room access can still reach the list through the room. Revoking the public token does not revoke room membership. Removing room members is a separate room-password/authorization concern.

One token is shared by everyone using that link, so rotation revokes access for everyone at once. Individual user revocation would require user accounts or separate per-recipient tokens and is outside this plan.

## Existing links and rollout

Existing `/list/{slug}` links are currently the weak links. To fully fix the guessing problem, they cannot remain publicly usable forever.

Recommended rollout:

1. Add and backfill secure tokens.
2. Update room list buttons and share buttons to use the new canonical links.
3. Give users new links for lists they have shared.
4. Retire the old public slug route, or make it require room authorization instead of serving the list publicly.
5. Do not redirect old public URLs to new URLs: a redirect would reveal the new token to anyone who guessed the old URL.

This may require users to replace saved or shared list links. It does not affect room passwords, room restart persistence, the PWA installation, `start_url`, or `scope`.

A temporary compatibility period is possible, but while old links remain public the original 24-bit weakness remains for those links.

## PWA and restart requirements

Do not change:

- the manifest `start_url` (`/`);
- the manifest `scope` (`/`);
- the root route's remembered-room behavior;
- the room access-token design from `plans/room_access_tokens.md`.

List share tokens are independent of room access tokens. They are stored in the database and used only for public list links. Deploying or restarting the server must not invalidate them unless they are deliberately rotated.

## Suggested implementation order

1. Decide on the canonical public route, preferably `/share/{token}`.
2. Add the token column/table and migration for existing lists.
3. Generate secure tokens for new and existing lists.
4. Add token-based list lookup and route handling.
5. Update room navigation and share-link generation.
6. Add token rotation/revocation in the appropriate list-management UI.
7. Retire or restrict the old slug route.
8. Update architecture and deployment documentation if the public URL contract changes.

## Tests and acceptance criteria

- New tokens are generated with at least 128 bits of randomness.
- Tokens are unique and are not derived from list names.
- A valid token opens only its associated list.
- A wrong, incomplete, or invalid token does not expose a list.
- Changing a list name does not invalidate its token link.
- Rotating a token invalidates the old link and makes the new link work.
- Room access still works after a server restart and does not depend on list share tokens.
- Public links remain editable, matching the current architecture.
- Old public slugs are no longer an unauthenticated way to access lists after rollout.
- PWA installation and home-screen navigation remain unchanged.

## Alternatives

- Keep the current six-character suffix: simplest, but leaves the guessing risk.
- Replace the suffix with a 128-bit token: secure and smaller implementation, but mixes the readable slug and secret token and is less flexible for future sharing.
- Use separate per-user tokens: stronger revocation control, but requires user identity or an invitation system.

## Progress tracking

- [ ] Decide and document the canonical public route
- [ ] Add token schema and migration
- [ ] Generate and look up secure tokens
- [ ] Update list navigation and share links
- [ ] Add token rotation/revocation
- [ ] Retire or restrict old public slug URLs
- [ ] Add automated tests
- [ ] Perform manual link and PWA checks
