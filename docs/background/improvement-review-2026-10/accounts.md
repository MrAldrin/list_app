# ListR: accounts, cross-room lists and admin. Design options

Status: research and design only. No code changed. No file in `/home/hsa/projects/list_app` was edited.
Basis: `ARCHITECTURE.md`, `docs/api.md`, `docs/room-invitations.md`, `docs/public-sharing.md`,
`docs/home-screen-installation.md`, `plans/advanced_sharing.md`, `plans/backlog.md`, and the code in
`src/` and `frontend/src/lib/admin`, `frontend/src/lib/room`.

## 0. Key findings

- **Access is checked in one place.** Room access goes through `_valid_room_id_for_token_locked`
  (`src/database_crud.py:567`) via `room_token_transaction` and `token_access`
  (`src/api/access.py`). Share links use a similar single check (`share_token_transaction`).
  Adding accounts therefore touches few lines in the auth path.
- **A browser already holds one token per room.** Each room has its own cookie
  (`listapp-room-<sha256(slug)>`, `src/room_cookies.py`). The missing piece for a switcher is a list
  of slugs. `last-room` stores only one slug.
- **Cross-room sharing does not strictly need accounts.** A browser that holds both room tokens can
  link a list from room A into room B. The limit: a partner who only knows room B cannot link a list
  from room A. Accounts are what remove that limit.
- **The hard part of cross-room lists is change tracking, not auth.** `changed_seq` is stamped from
  the list's owner room (`src/database_setup.py:260-290`). Deletions are keyed by `room_id`. Live
  streams wake by `room_id` (`src/api/ops.py:673`). A second room would miss changes unless this is
  redesigned.
- **Nothing records who did a change.** No table or column has an author, actor or owner field
  (checked `src/`). "Who did what" needs new columns.
- **The owner's "remove one person" need is not served today.** The only revoke is a room password
  change, which signs out every device and forces a new password on everyone (`docs/api.md`, Room
  management).

## 1. Problems today

### Admin UX

1. **Two passwords and two sign-ins.** The admin uses `APP_PASSWORD` at `/admin`. Each room has its
   own password. The owner must remember both.
2. **No way from inside the app to `/admin`.** `Brand.svelte` is a plain span, not a link. The room
   menu (`frontend/src/lib/room/RoomMenu.svelte`) has no admin entry. The only Admin button is on the
   start page `/` (`frontend/src/routes/+page.svelte:105`). The installed home-screen icon opens the
   room directly (`docs/home-screen-installation.md`), so the owner cannot reach `/` from it.
3. **Entering a room needs its password.** The room link from the admin list opens
   `/room/{slug}?admin=true`. That page still shows the password prompt
   (`frontend/src/routes/room/[slug]/+page.svelte`). Admin login never gives room access, by design
   (`docs/api.md`, Admin).
4. **The only shortcut is a reset, and it is disruptive.** To get in, the admin resets the room
   password. The reset signs out every device in that room (`ResetPasswordDialog.svelte`,
   `api/admin.py` reset_password). The admin also sets the new password, so the admin always knows it.
5. **Thin overview.** `GET /admin/rooms` returns only name and slug (`api/admin.py` `_room`). There is
   no list count, member count or last activity.
6. **Admin sessions cannot be listed or ended one by one.** The admin cookie is stateless and signed
   with a key from `APP_PASSWORD` (`src/admin_access.py`). The only global end is changing
   `APP_PASSWORD`. The cookie lasts 14 days.
7. **Admin sign-in lockout is global.** 10 failed admin sign-ins block everyone for one minute
   (`src/sign_in_limiter.py`, `ADMIN_LIMIT = 10`). A bad actor can block the owner.
8. **The "Home" room password starts equal to `APP_PASSWORD`, then drifts.** `_ensure_default_room`
   sets it only on first setup (`src/database_setup.py`). Later changes to `APP_PASSWORD` do not
   change the Home room. This is a trap for the owner.

### Access model

9. **One shared key per room.** Everyone with the room password can rename, change the password and
   delete the room (`docs/api.md`, Room management).
10. **No per-person identity.** No author fields exist. "Who added or checked this item" cannot be
    answered.
11. **A list belongs to one room.** `lists.room_id` is a single value. Writes look up lists with
    `list_id_for_uid_locked(room_id, uid)` (`src/api/ops.py:339`).
12. **Share links are the only cross-room workaround.** A share link opens one list with no room
    context, and its token sits in the URL. Only room members can reset it. A partner cannot manage
    it from their room.
13. **Min 4-character room passwords** (`docs/api.md`, Room password rule). Sign-in limits are kept in
    memory per room and reset on restart.

## 2. Options

Sizes are rough: S = one focused change, no migration. M = a few changes, one small migration. L =
several steps with new auth and UI. XL = replaces the current model.

### Option A: Keep rooms. Add in-app admin entry and a room switcher

**What it is.** Two small UI features on the current model.

- **A1 Admin entry.** An "Admin" item in the room menu and in the room header. It shows only when
  this browser has signed in as admin before. The item goes to `/admin`. Admin sign-in still needs
  the app password.
- **A2 Room switcher.** A "My rooms" menu. The start page `/` opens the last room, as today.

**User flow.**
- A1: Open the room menu, tap "Admin", enter the app password once, manage rooms.
- A2: Open the menu, pick another room from the list. The app asks for its password only if the
  browser has no valid token for it.

**Data model.** None on the server. A1 needs a non-secret hint cookie, `listapp-admin-hint`, set by
`POST /admin/session`. A2 needs a cookie listing known room slugs (for example `listapp-rooms`, a
JSON array of slugs, capped at about 10).
- Use a cookie, not localStorage. Per `docs/home-screen-installation.md`, iOS copies cookies into the
  installed app, and localStorage is not copied.

**Security.** No new trust. Slugs are routing hints, not secrets. The hint cookie does not grant
anything. The switcher still asks for a password when the token is missing or revoked.

**Migration.** None. Existing cookies stay valid.

**Effort.** S for each part.

**Risks.**
- The hint can go stale (the admin cookie expired). A1 then shows the sign-in prompt, which is
  acceptable.
- The slug list can list rooms that were deleted. Clicking one shows "Room not found" or the password
  prompt. This is the same as today.

**What it unlocks.** Admin is reachable from the installed app. The owner can move between "my room"
and "partner room" without typing URLs. No accounts needed.

### Option B: Cross-room list links

Same underlying data for both variants. Only the auth rule for creating and managing a link changes.

**Data model (both variants).**

```sql
CREATE TABLE list_room_links (
  list_id   INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
  room_id   INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,  -- the room that shows it
  created_at TEXT NOT NULL,
  created_by_user_id INTEGER,              -- variant B2 only; NULL for now
  PRIMARY KEY (list_id, room_id)
);
```

Plus the changes below.

- **Scoping.** `list_id_for_uid_locked` and `get_list_changes_locked` must accept a list if
  `lists.room_id = ?` **or** a link row exists. Ops, feed and `deletions` need the same rule.
- **Change tracking (the hard part).** Options:
  1. Per-list seq, as `share_seq` already does (`get_share_seq_locked`). The feed for a room returns
     a linked list when that list's own seq is past the room's cursor. Smallest change; changes the
     cursor shape for linked lists only.
  2. A global change seq across rooms. Cleaner, but every offline client must reset its cursor once.
     This needs an API version bump (`docs/api.md`, API version).
- **Deletions.** A list deleted by its owner must appear as a deletion in every linked room. Today
  `deletions` rows carry one `room_id`. Either write one row per linked room, or join through
  `list_room_links` when reading.
- **Streams.** A write must wake the streams of every room that shows the list
  (`notify_room_changed` called for each room).
- **Names.** The unique index `(room_id, name NOCASE)` only covers a room's own lists. A linked list
  can collide with a list named the same in the destination room. Decide: refuse the link, or show
  both.

**Variant B1: link by holding both room tokens (no accounts).**
- **User flow.** In room A, open a list menu → "Show in room B". The app asks for room B's password
  if the browser has no token for it. Only a browser that holds both tokens can create the link. The
  endpoint checks both tokens in one transaction, which SQLite allows.
- **Who can do what.** Anyone with B's token can unlink in B. Room A's members manage the list as
  today. Decide whether B's members may rename, tag, delete or
  visibility-change a linked list. Suggested default: they can check items and edit items; they
  cannot delete the list (only the owner room can).
- **Security.** Works with today's model. The room tokens stay the only proof. Password change in
  room A does not remove links. Decide: keep the link (B still edits A's list) or drop it. Suggest
  dropping links from the room whose password changed.
- **Migration.** Additive table. Existing rows are untouched.
- **Effort.** M to L. Touches ops scoping, feed, deletions, streams, tests, and the Svelte room
  list.
- **Risks.** The partner cannot link their own list into the owner's room without the owner's
  password for room A. The change tracking must be right, or partners silently miss updates.
- **Unlocks.** Owner and partner can see the same list in both rooms, with no accounts.

**Variant B2: link by account membership (after Option C).**
- **User flow.** A member of both rooms (via account memberships) links a list. The partner can link
  their own list into the owner's room.
- **Security.** Membership replaces the two-token rule. Links can be audited with
  `created_by_user_id`.
- **Effort.** S on top of B1 once C exists. Only the auth check changes.

**Risks common to B.** `plans/advanced_sharing.md` describes pinning with a dashboard. B1 is simpler:
a link is a shared list, not a pinned card. Pick one name and one UX before building.

### Option C: Optional accounts layered on rooms

Rooms and room passwords keep working. Accounts add an optional login. Accounts unlock extras. A
person without an account keeps using room passwords exactly as today.

**Login method choices.**

| Method | Pros | Cons |
|---|---|---|
| Username + password (bcrypt, as rooms) | Simple, reuses `password_hashing.py`, `SignInLimiter`. No new service. | Typed passwords, weaker than passkeys. |
| Passkeys (WebAuthn) | Face ID on iPhone. No password to share. | New library (for example `py-webauthn`). Tied to the domain: a domain change breaks logins. Needs a fallback. |
| Magic link (email) | No password. | Needs an email provider (third party, cost, deliverability). Adds a dependency the app does not have. |

Suggest: username + password first. Add a passkey later as an extra login for the same account.

**User flow.**
1. Owner creates an account invitation (admin page, same style as room invitations) or the owner's
   admin creates the account directly.
2. The person opens the link, picks a username and password, and gets a personal room (optional).
3. Signing in shows the rooms the account belongs to. Rooms also still open with the room password.
4. Joining an existing room with its password adds that account as a member. Anyone who knows the
   password can join. This is no more power than today.

**Data model.**

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  uid TEXT NOT NULL UNIQUE,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  display_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,      -- only if A2/A3 chosen; see section 3
  created_at TEXT NOT NULL,
  disabled_at TEXT
);
CREATE TABLE user_sessions (                  -- same pattern as room_access_tokens
  id INTEGER PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE TABLE room_members (
  room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
  added_at TEXT NOT NULL,
  PRIMARY KEY (room_id, user_id)
);
ALTER TABLE rooms ADD COLUMN owner_user_id INTEGER;   -- personal room; NULL for old rooms
ALTER TABLE items ADD COLUMN added_by_user_id INTEGER;  -- "who did what", NULL for old rows
ALTER TABLE items ADD COLUMN done_by_user_id INTEGER;
```

- Account sessions are server-side and revocable. This is better than the admin cookie. Add "sign out
  other devices" for free.
- `room_token_transaction` accepts a room if a room token matches **or** the account session is a
  member of the room. One chokepoint.

**Features that need an account (the owner's "a few more features").**
- Personal room created at sign-up.
- "My rooms" list from memberships (replaces the cookie list from A2 for account users).
- Cross-room linking with membership (B2).
- "Who did what": `added_by_user_id`, `done_by_user_id` shown in item details. Old rows show nothing.
- Remove one person: delete the membership. This only ends account access. Anyone who still knows
  the room password keeps access, so a password change is still needed for a full cut-off.
- Notifications (later): web push needs VAPID keys and a push handler in the existing service worker.
  Only for installed iPhone users (iOS 16.4+). Needs its own plan.

**Security implications.**
- New login surface. Add `SignInLimiter` keys per username and per account. Do not trust client IP
  (`docs/api.md`: no trusted client address on Railway).
- Account invitations must be single-use or expiring, like room invitations. Otherwise any leaked
  link creates accounts.
- Recovery: no email. Lost password = admin reset, as rooms do now. Admin reset must be audited
  or at least shown in the admin list.
- Keep `APP_PASSWORD` admin as the fallback. Do not let an account role lock the owner out.
- Items gain an actor. Make sure share links and anonymous ops set `NULL`, not a guessed id.
- The admin cookie stays stateless unless A2/A3 changes it.

**Migration of existing data.**
- None required. Existing rooms have `owner_user_id = NULL` and keep room-password access.
- Optionally, when an account first joins an old room, that account becomes `owner` if the room has
  no owner yet. Keep it simple: `member` for everyone, and the owner's account is the one created
  first.
- Old items keep `added_by_user_id = NULL`.

**Effort.** L. New tables, login and sign-up UI, session middleware equivalent, account invitations,
item actor fields, tests across Python and Svelte, and doc updates. Passkeys add another M.

**Risks.**
- The largest risk is scope creep. Accounts touch auth, which is the area `ARCHITECTURE.md` treats
  carefully.
- Two ways to get in (room password and account) can drift. A password reset should not leave an
  account still in the room unless the owner wants it.
- Usernames: decide who picks them. Owner can create accounts for the partner to avoid a public
  sign-up.

**What it unlocks.** Personal room, one login for many rooms, who did what, remove one person,
partner's own identity, cross-room linking (B2), and later notifications.

### Option D: Full account model replacing room passwords

Every access goes through accounts. Room passwords are removed. Rooms have owners and members.

**What changes.** Everything in C, plus:
- Migrate each existing room to an owner account. This needs a "claim" step: the first person who
  signs in with the room password becomes its owner. Until claimed, the room keeps its password.
- Remove room password sign-in, the room cookie and `room_access_tokens`, or keep them only as a
  join code.
- Rewrite `docs/api.md` (Room session, Sign-in limit), `ARCHITECTURE.md`, and the offline cookie
  behaviour in `docs/home-screen-installation.md`.

**Security.** Strongest per-person control. But the attack surface moves to accounts entirely, and
an account recovery path becomes mandatory.

**Migration.** Risky. A bad claim or a lost owner account can lock a room out. Five users with
phones make a recovery flow hard to test.

**Effort.** XL.

**Risks.** Breaks home-screen installs and saved cookies. Lockouts. Big change to documented
invariants. The owner's needs are met by C with less risk.

**Unlocks.** A single clean model. Not needed for the stated goals.

**Recommendation on D:** do not build now. Revisit only if C works and the owner wants room passwords
gone.

## 3. Admin redesign ideas

| Idea | What it is | Pros | Cons |
|---|---|---|---|
| **A1 In-app entry** (from Option A) | "Admin" item in room menu, shown when the admin hint cookie is set. | Small. No new security. Solves "cannot reach /admin". | Admin still uses a second password. |
| **A2 Admin as an account role** | `users.is_admin`. Admin signs in with a normal account. Destructive actions (reset, delete room) ask for the account password again. | One login. Admin sessions revocable, unlike the stateless cookie. | Needs Option C first. The owner's account becomes a single point of failure. Keep `APP_PASSWORD` as a break-glass fallback. |
| **A3 CLI-only admin** | Management commands (`python -m admin rooms`, `reset-password <slug>`, `invite`) run on the server, not in the browser. | Removes the admin web surface. Simple. Good for rare tasks. | Needs a way to run commands in the Railway container. **Not checked here.** Less friendly for the owner. |
| **A4 Read-only room view for admin** | Admin can see a room's lists without its password. | Solves "I need to look at a room" without resets. | **Conflicts with a stated invariant** (`docs/api.md`: admin never grants room access; a documented invariant). Needs an explicit decision and doc change. Also: the server operator can read the database anyway (`ARCHITECTURE.md`: rooms are not private from the server administrator). |
| **A5 Generated reset passwords** | Reset shows a random password once; the admin does not choose it. | Admin does not hold a chosen password. Small change. | Owner still needs to pass the password on. |
| **A6 Richer overview** | Show list count, last change, member count per room. | Useful for cleanup. | Needs counts in `get_rooms` (cheap). No content leak. |

**Suggested admin path.** A1 now, A5 and A6 with it if wanted. Choose between A2 and A3 after Option C.
Do not choose A4 without the owner's explicit decision.

## 4. Recommendation and path

**Recommendation.** Do not start with accounts. Start with the two small UI changes (A1 and A2). They
fix the pain the owner reports today. Then add cross-room links with room tokens (B1), because the
owner already holds both passwords. Add accounts (C) when the owner wants "who did what", a personal
room, or removing one person without a new password. Skip D.

**Why push back on "accounts first".** The owner's two goals split. "Share lists across rooms" works
with room tokens for the owner. "Personal room, who did what, remove one person" needs accounts. Do
not build accounts just to get the first goal.

**Path. Each step ships on its own.**

1. **A1 Admin entry in the room menu.** Hint cookie set by admin sign-in. No migration. Tests: menu
   shows only with the hint; the link goes to `/admin`.
2. **A2 Room switcher.** Cookie with known slugs, capped. No migration. Tests: order, cap, removed
   rooms.
3. **A5 and A6 (optional).** Small admin changes. No migration (A6 is a query).
4. **B1 Cross-room links with room tokens.** Migration: one new table `list_room_links`. Change
   tracking: per-list seq for linked lists (option 1 above). Decide the open questions first (below).
   Update `ARCHITECTURE.md` "Lists belong to one room" and `plans/advanced_sharing.md`.
5. **C0 Accounts foundation, hidden.** Migration: `users`, `user_sessions`, `room_members`.
   Account invitations. Username + password sign-in with `SignInLimiter`. No user-visible change
   for people without accounts.
6. **C1 Personal room and "my rooms".** Account creates a room. Room menu lists memberships. Room
   tokens still work.
7. **C2 Who did what.** Migration: `added_by_user_id` and `done_by_user_id` on items. Show in item
   details. Old rows stay empty. Check API version rule for new fields (no bump for added fields).
8. **C3 Remove a member.** Delete membership. Optional: passkeys.
9. **B2 Membership-based links.** Replace the two-token check with membership. Small change after C0.
10. **A2 or A3 admin role.** Only after C0 and owner decision.

**Questions the owner must answer before step 4.**
1. Can a partner who has only room B edit a list linked from room A? Suggested: items yes, delete no.
2. If room A's password changes, do its links to room B stay? Suggested: drop them.
3. Does admin ever see room content without its password? Suggested: no (keeps the invariant).
4. Username + password now, passkeys later: OK?
5. Is "who did what" worth a schema change? Only the owner can judge.

**Docs that change with these steps.** `ARCHITECTURE.md` (room and admin boundaries, "no individual
accounts", "lists belong to one room"), `docs/api.md` (admin and sign-in sections),
`docs/room-invitations.md` (line "Future personal accounts can replace room-password authorization"),
`docs/public-sharing.md` (share rules, only if links change), `plans/backlog.md` (items for Admin
entry, user profiles, cross-room pinning).

**Tests to keep green at every step.** pytest (API and DB), the browser suite on Chromium, Firefox and
WebKit, and the Android suite where relevant (per `AGENTS.md`).
