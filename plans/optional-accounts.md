# C: Optional personal accounts alongside rooms

Lifecycle: tracked

## Decision and scope

The owner asked for a written plan for optional accounts, not a build. The
current choice is still to keep room-password access and not add cross-room
sharing or accounts yet; see [the recorded decision](decisions-for-heming.md#4-sharing-a-list-across-rooms).
This assessment covers C (accounts layered on rooms), not D (accounts replacing
room passwords). It does not authorize implementation or change the separate
`APP_PASSWORD` admin login.

## Approval gate

The owner must explicitly select C and authorize implementation before work
starts. Agree on its room-authorization and account-recovery boundaries, and on
any required `ARCHITECTURE.md` changes, first. This plan does not approve an
admin redesign, membership policy, or data migration.

## Current state

- **Implemented today:** Rooms use shared passwords and room-specific
  HttpOnly cookies. A valid room token grants the room's existing shared
  capabilities; the server rechecks authorization for private reads and writes.
  See [room sessions](../docs/api-rooms.md#room-session), the
  [API auth model](../docs/api.md#auth-model), and `src/api/access.py`.
- **Implemented today:** Admin uses a separate app password and cookie; admin
  sign-in alone does not grant room access. Existing room-creation invitations
  create rooms, not accounts or memberships. See [admin](../docs/api-admin.md#admin)
  and [room invitations](../docs/room-invitations.md).
- **Not implemented:** There are no `users`, account sessions, room memberships,
  or actor fields recording who changed an item. No email delivery or passkey
  service is part of the current stack.
- **Verified:** This assessment read the cited docs, code, and the earlier
  [accounts design report](../docs/background/improvement-review-2026-10/accounts.md).
  No account behavior has been implemented or tested here.

## Assessment proposal (not approved)

Keep room passwords as a working access path for people without accounts. An
account should add a user identity and an optional way to reach explicitly
joined rooms; simply signing in must not grant access to every room or admin.
A possible minimum foundation is users, revocable server-side account sessions,
and room memberships. Account requests would be checked against membership at
the server authorization boundary; the existing room-token path remains
available. A username/password login is the smallest option using current
password hashing, but signup, recovery, and rate limits still need a deliberate
design. Do not assume email, magic links, or passkeys: no provider or
WebAuthn system is currently part of the app.

C should start only when a concrete need justifies the additional login system,
such as “who did what”, one identity for many rooms, or removing an individual
account. Accounts are not required for B1 when one browser already has both room
passwords. Cross-room links and accounts are separate decisions.

### Permission and revocation limits

- Decide how an account becomes a member: an invitation, an existing room
  password, an owner action, or some combination. Signing in is not enough.
- If someone can still use the shared room password, removing their account
  membership does **not** fully remove their room access. Changing that password
  is still needed to revoke the shared credential. State this limitation in the
  UI and docs if C proceeds.
- Account sessions should be revocable and checked server-side. Do not treat an
  account login as an admin role or as permission to inspect rooms. Keep
  `APP_PASSWORD` as a separate admin path unless the owner explicitly approves
  an admin redesign.
- If the app later records actors, represent room-password and public-share
  edits as unknown/anonymous, not as whichever account happens to be signed in
  in another tab. Define which actions are attributed and whether old data stays
  unattributed.

### Data, migration, and offline impact

An additive schema for users, sessions, and room memberships is a starting
point, not a final migration. Existing rooms should remain usable without
accounts; their owners/memberships and historical item actors should not be
invented. If optional personal rooms or activity history are selected, they
bring separate room/item schema work and UI beyond the login foundation. Keep
any migration non-destructive and backfilled values honest.

Account sessions add another cookie and sign-in path, and account membership
must be checked for every private room read/write; cached client state is never
authorization. Preserve same-origin write checks and sign-in throttling. A
username/password endpoint needs a per-account/username strategy in addition to
global protection; client IP is not a trustworthy limiter key in the current
hosting setup. Password recovery is unresolved because there is no email
provider.

Offline snapshots and queued writes are currently scoped to a room or public
share link, not an account. Keep pending room changes held until the room is
reauthorized after sign-out or session expiry; account sign-in must not silently
release a queue for a room the account is not a member of. Test cookie transfer
and logout behavior in installed browsers against the
[home-screen guide](../docs/home-screen-installation.md) and preserve existing
room-password users. Decide whether one account sign-out clears cached room
views, and avoid discarding queued edits without telling the user.

Keep additive API endpoints/fields compatible where possible. Revisit the
[API-version rule](../docs/api.md#api-version) if existing room request meaning,
write authorization, or response shapes change. The top-level architecture
currently documents room-password access and separate admin access; owner
agreement is needed before changing those security boundaries or updating
`ARCHITECTURE.md`.

## Possible stages if C is approved later

1. Agree on the use case, signup/invitation, recovery, session lifetime, and
   membership rules. Decide whether a personal room is in scope.
2. Add account identity and revocable sessions without changing existing room
   password behavior. Test access isolation before exposing account UI.
3. Add membership and room selection. Decide explicitly whether entering a
   room password grants that account membership, and document the shared-password
   revocation limit.
4. Only if selected, add actor attribution or per-person removal. Those are not
   automatic consequences of adding a login and need their own data and privacy
   decisions. Defer passkeys, email recovery, account-based admin, and
   notifications unless a separate need is approved.

## Limitations and examples

- A person with an account but no membership in room A must still be denied room
  A's data, even if signed in or an admin.
- A non-account user keeps opening a room with its password. Existing room
  tokens and public list links keep their current, separate meanings.
- Removing one person's membership is not enough if that person still knows the
  room's shared password or has another valid room token.
- “Who checked this?” cannot be inferred for old items or for edits made through
  anonymous room-password/public-share access.
- Accounts increase sign-in, recovery, session, migration, and offline test
  surface for a group of about five people; they are not a lightweight alias
  for the current room switcher.

## Tests required before calling a future implementation verified

Cover schema migration while preserving legacy rooms and tokens; signup or
invitation rules; password hashing, rate limits, recovery, cookie flags, expiry,
revocation, and logout; denied access without membership; room-password and
public-share compatibility; `APP_PASSWORD` admin isolation; same-origin writes;
role changes and account removal while sessions are active; and API version
compatibility. Exercise offline snapshots and held queues across sign-out,
session expiry, re-login, room deletion, and membership removal. If actor fields
are chosen, test anonymous actions, old rows, attribution boundaries, and any
export/deletion behavior. These are recommendations, not tests run by this
plan.

## Questions for Lead

1. Which concrete user problem makes optional accounts worth maintaining, and
   which account-dependent features are actually wanted: personal room, room
   switcher, activity history, individual removal, or something else?
2. Who can create an account, and how can a user recover it without an email
   service? Can a room password create account membership?
3. What exactly grants account access to a room, and what happens to existing
   room tokens when membership is removed?
4. Should accounts ever carry admin permission, or should `APP_PASSWORD` remain
   separate? (This plan assumes separate admin access.)
5. Is a personal room part of C, or a later independent feature? What activity
   is attributed, and how are edits through room passwords or share links
   represented?
6. What session lifetime and offline sign-out behavior are acceptable?

## Progress

- [x] Read current room/admin auth, invitations, offline and home-screen
  behavior, plus the earlier account assessment.
- [ ] Lead reviews the use case and unresolved permission/recovery choices.
- [ ] No implementation is authorized by this plan.
