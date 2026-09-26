# Room-specific home-screen launch and remembered access

## Why the root and admin routes stay separate

The root (`/`) remains a public router, not the admin login page. It supports
remembered-room recovery for older installations and pages that do not belong
to a specific room. The admin tools stay at `/admin`, behind the global app
password.

New room installations can request `/room/{slug}` as their launch address.
The app still keeps the root manifest identity and `/` scope so existing icons
and navigation between room and list pages continue to work. This arrangement
avoids the old iOS failure where every home-screen launch opened an admin login
page, while retaining a safe fallback for installations that use the root
manifest.

## Behavior

- Install from `/room/{slug}` to request that room as the launch address, even
  if the page currently shows its password prompt. Installation does not grant
  access: a fresh installation without a valid token still needs the password.
- Open the room before installing, rather than installing from a public list,
  invitation, admin page, or the root page. Those pages retain `/` as their start
  address, with the existing remembered-room/link-entry recovery.
- Room manifests contain only the public routing slug, never passwords, access
  tokens, room names, invitation links, or `admin=true` parameters.
- ListR retains `id: "/"` and `scope: "/"`. We deliberately do not introduce
  separate app identities per room, which could create duplicate installations
  and change existing app identity. Browsers may reuse an existing installation.
- Switching rooms works as before but does not deliberately retarget the icon.
  The manifest requests the installation room, not the most recently used room.
- Existing icons may retain their root launch address. No automatic conversion
  or preservation of an existing icon's launch address is promised: manifest
  update behavior is browser-controlled. Keep the room link and password before
  removing/reinstalling an icon; deleting it may remove its saved login.
- Deleted-room links still show “Room not found”; they never grant access to a
  different room. Open another saved room link or the site's root to recover.
- HTTPS sign-in now stores the existing revocable token in a host-only Secure,
  HttpOnly, SameSite=Lax cookie with a one-year lifetime. No database migration
  or new permission is needed. Password changes still revoke every old token.
- Existing localStorage tokens migrate on their next read, after server validation
  and a second request confirming cookie acceptance. Only then is the old token
  removed. HTTP development and cookie failures retain localStorage fallback.
- The goal is no additional sign-in after installation where cookies are copied.
  [Apple documents copying cookies from iOS/iPadOS 17.2 onward](https://webkit.org/blog/14787/webkit-features-in-safari-17-2/).
  Existing installations and other browsers may behave differently. Cookies are
  not assumed to stay synchronized between Safari and the installed app.
- Install only after sign-in finishes (or after reopening an existing signed-in
  room so its legacy token can migrate). Expired, cleared, blocked or revoked
  credentials always require another sign-in.

## Read-only offline viewing on a prepared browser

While an authorized room or private-list page is open, ListR quietly saves all
lists and items in that room, including lists you have not opened and completed
items. The saved view is simpler than the online editor: it shows names, details,
tags, quantities, and completion state, but cannot change anything. It displays
“Offline · read only” and “Last saved” so you can judge whether changes made
elsewhere are missing. Reopening a room or private list, returning to its tab,
reconnecting, or completing an authorized edit attempts to refresh the copy.
Updates require an open app and a successful server check; closed-app background
sync is not promised.

To prepare before shopping, open your room online and sign in. The app does
not yet show a positive “ready” indicator; to confirm a copy exists, briefly
switch your device offline and open the room from its icon/link, then check that
all expected lists appear with a “Last saved” time. If you see “No offline copy
is ready,” do not rely on offline viewing. Browser storage can fail or be
cleared/evicted, and Safari and installed-app storage may differ.
Only one room is saved per browser origin: visiting another authorized room
replaces the prior complete copy. This does not change online access to rooms.
Older icons opening `/` can use the saved room; room URLs must match the saved
room. Deep `/list/` bookmarks and `/share/` links are not offline launch paths.
An already-open online page shows a passive link to saved lists when the browser
signals a lost connection; its live editing controls should not be treated as
working offline.

On reconnection a definitive authorization denial clears the matching offline
copy. A temporary network/database/storage failure retains the previous copy
and its old timestamp, with a warning. Password changes or room deletion cannot
erase a disconnected phone immediately: anyone with access to a shared/lost
phone may still read its downloaded lists until it reconnects. Clearing the
browser's site data also removes the copy (and may remove saved sign-in).
Public share links are online-only; no token, room password, or private page
HTML is put in the service-worker cache.

Desktop Chromium/Firefox automated checks verify local HTTP behavior; they do
**not** prove that an iPhone/Android installed app will launch offline, retain
storage, or share Safari's login. Complete the real-device checklist below
before relying on installed-app offline viewing.

## Implementation and automated checks

`src/main.py` serves `/room-manifest/{slug}.json` from the same base manifest as
`/manifest.json` and `/static/manifest.json`, overriding only `start_url`.
Room responses prohibit caching. Unknown/deleted rooms return 404. Each page
adds exactly one client-local manifest link; room metadata is not shared across
visitors. Links are added before browser-storage awaits, so they are available
in the initial page head rather than relying on a later JavaScript replacement.

Tests cover defaults, stable identity/scope, distinct rooms, secret/query
exclusion, escaping, deleted rooms, client isolation, password prompts and
installation instructions. Existing room access/routing tests cover token
validation and remembered-room recovery. These are not substitutes for device
installation checks.

## Room authorization and token persistence

`src/database_crud.py` checks bcrypt room-password hashes and issues opaque,
random room access tokens. SQLite stores only each token's hash, room ID, and
room authorization version. Validation checks the room, matching version, and
revocation state. Changing/resetting a room password increments that version and
deletes old tokens in the same transaction. Existing valid tokens can survive
server restarts because validation uses persisted database state.

`src/room_access.py` provides the private-page authorization context. Private
reads and operations must validate current access rather than trust the
`authorized_rooms` UI cache. Admin authentication and `?admin=true` do not replace
room authorization. Public `/list/{slug}` pages remain editable without room
credentials; navigating back does not bypass the room password prompt.

The legacy token key is `listapp_room_token_{slug}`. It is removed only after
cookie acceptance is confirmed. `listapp_last_room` and the separate last-room
cookie remember routing only, never permission to enter that room. Browser
storage does not retain room passwords.

Malformed or unsupported stored bcrypt hashes are rejected as invalid credentials
rather than raising a password-check exception. This does not automatically repair
stored data or require a migration; an admin password reset can restore access.
An old malformed local test fixture is not evidence of production corruption.

## Cookie security and deployment

`src/room_cookies.py` exposes a POST-only token-to-cookie bridge. Writes require
HTTPS, exact matching Origin, a custom request header, and token validation.
Cross-site Fetch Metadata is rejected. Cookie acceptance is checked without
returning credentials to JavaScript. Socket.IO uses same-origin handshakes rather
than NiceGUI's wildcard default, covering websocket and polling transports.
Normal private callbacks continue validating the token against the database.
The token still briefly passes through JavaScript during login/migration; this
is not a complete defense against malicious scripts on the app's own origin.

Cookies use `__Host-` names, no Domain attribute and path `/`. Host the app on a
dedicated trusted origin, not alongside unrelated applications. Each remembered
room adds a cookie; this is designed for a few rooms, not hundreds. Root routing
remembers the last sign-in/migration, not a guarantee to retarget an installed icon.

Railway must forward the original HTTPS scheme and host, and the server must
trust forwarded headers only from its proxy. A mismatched Origin/scheme rejects
cookie writes rather than weakening checks; localStorage fallback may still
work, but installation sign-in preservation then will not. Check HTTPS cookie
creation and websocket reconnects after deploying. Do not enable cross-origin
credentialed CORS or wildcard Socket.IO origins.

## Verification performed

- Cookie implementation: **229 tests passed**, with clean Ruff formatting/lint
  checks. No dependency changes or database migrations.
- Disposable HTTPS server plus real headless Chromium: verified password sign-in,
  Secure/HttpOnly cookie creation, removal of migrated localStorage tokens,
  fresh-context access with only copied room cookies, legacy-token migration,
  and password fallback after authorization-version revocation. This also checked
  that HTTPS websocket connections work with the same-origin restriction.
- Original room-launch implementation: **214 tests passed**, with clean Ruff checks.
- Cookie regression tests simulate copied cookies with no localStorage and cover
  cookie flags, confirmation, migration/fallback, revoked tokens, invalid requests,
  database failure and same-origin Socket.IO configuration. This does not simulate
  the operating system's Add to Home Screen operation.
- Started a disposable real app server with a temporary database. Fetched the
  initial HTML for a room, room with `admin=true`, missing room, root, admin
  login, invalid invitation, and missing public list. Each contained exactly
  one correct manifest link; each linked manifest had the expected start URL
  and stable identity. No production/developer database was used.
- The suite reports the existing Starlette/httpx deprecation warning; no
  dependency changes were made for this feature.

## Outstanding real-device acceptance checklist

In addition to the sign-in/install checks below, test this offline behavior on
an actual installed iPhone Safari app and Android Chrome app/shortcut using
only disposable rooms. Record OS/browser version, whether the service worker
controls the page and the snapshot is present, then enter airplane mode,
force-close and relaunch room and old-root icons, open every list (including one
never opened online), reconnect and observe changes/deletion/password revocation
from a second device. Repeat after clearing site storage and after an app/worker
update. These checks are **pending**, not inferred from desktop tests.

Use HTTPS and disposable rooms. Record OS/browser versions and results. These
checks have **not** been performed by the coding agent.

1. **Fresh iPhone installation:** in Safari, create/open room A, sign in, then
   Add to Home Screen. Launch the icon. On supported versions with cookies
   preserved, expect room A's lists without signing in again. If prompted, record
   that as a failed sign-in-preservation check (the password prompt remains a safe
   fallback). Repeat using an existing localStorage login after visiting room A
   to migrate it. Also test with browser storage disabled.
2. **Password-prompt installation:** install directly from room A's password
   page. Confirm the icon opens A but does not reveal its lists without login.
3. **Restart:** close/reopen the installed app and restart the server. Confirm
   valid remembered access still works. Change the password elsewhere and
   confirm revoked access prompts again, without revealing private data.
4. **Old icon:** before upgrading, install an icon using the old root manifest.
   After upgrading, test with valid, missing, and revoked saved access. Confirm
   normal recovery remains available; record whether the icon's address changes.
5. **Multiple rooms:** visit A and B in separate tabs, install from A, and check
   the launch address. Switch to B, close, reopen, and record behavior. Try
   installing from B with A already installed; the browser may reuse the app.
6. **Other pages:** verify root/public-list/admin/invitation pages advertise only
   the default manifest, without private room metadata or invitation tokens.
7. **Deleted room:** delete a disposable installed room and launch its icon.
   Expect “Room not found”, not another room's private data.
8. **Android Chrome:** repeat fresh install, restart, old icon, multiple rooms,
   and password revocation checks. Check both installation and shortcut options
   if the browser offers them.

Do not remove a user's working icon just to test. Use a spare device/profile
where possible. Retain the root manifest/routes for older installations.
