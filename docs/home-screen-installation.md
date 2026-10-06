# Home-screen installation and remembered room access

## How to install

Open the room, sign in, then use **Add to Home Screen**. The room menu (⋮)
has an **Add to Home Screen** entry with the steps. The icon then opens
that room directly. On iOS 17.2+ the login cookie is usually copied into the
installed app, so no second sign-in is needed.

- Installing from the room's password page also works, but the icon will still
  ask for the password.
- Installing from any other page (root, public list, admin, invitation) gives an
  icon that opens `/`, which sends people to their last remembered room.
- Expired, cleared, blocked or revoked logins always ask for the password again.

## Behavior

- **Launch address:** `/room/{slug}` pages link a room manifest whose
  `start_url` is that room. All other pages use the default manifest (`/`).
- **One app identity:** every manifest keeps `id: "/"` and `scope: "/"`, so
  rooms do not become separate apps. A browser may reuse an existing install.
- **No secrets in manifests:** only the public room slug. Never passwords,
  tokens, room names, invitation links or `admin=true`.
- **Apple icon:** pages declare the home-screen icon. The conventional
  `/apple-touch-icon.png` and `/apple-touch-icon-precomposed.png` paths serve
  the same image for browsers that request those paths directly.
- **Switching rooms** does not retarget an installed icon.
- **Old icons** may keep opening `/`. Browsers decide whether to update them.
  Deleting an icon may also delete its saved login.
- **Deleted rooms** show "Room not found" and never open another room.
- **Root `/`** is a public router, not the admin login. Admin stays at `/admin`.

### Svelte app

The Svelte app is served at `/`. The same rules apply:

- The room page links `/room-manifest/{slug}.webmanifest`
  (`start_url` `/room/{slug}`). Every other page links
  `/manifest.webmanifest` (`start_url` `/`). The link changes when
  the page changes inside the app.
- Icons made while the app ran under `/app/` (phone testing) still open: the
  server redirects `/app/...` to the same address at `/`.
- Both are made from `src/static/manifest.json` (`src/install_manifest.py`), so
  `id` and `scope` stay `/`: one app identity, the same as the earlier app's installs.
- The room manifest does not check that the room exists, because the Svelte
  app never tells. A deleted room's icon shows the password prompt, and
  signing in says "Wrong room or password."
- Icons are the files under `/static/icons/`.
- No service worker yet. `/sw.js` only removes the old app's worker ([decision 159](../plans/svelte-frontend-rewrite.md)).

## Remembered access

- Signing in to a room issues a random access token. The database stores only
  its hash, tied to the room's authorization version.
- On HTTPS the token lives in a `__Host-` cookie: Secure, HttpOnly,
  SameSite=Lax, one year. On plain HTTP (local development) it falls back to
  localStorage.
- Old localStorage tokens move to the cookie on the next visit, and are removed
  only after the cookie is confirmed.
- Changing or resetting a room password revokes every existing token for that
  room.
- The admin password does not grant room access. Public share links do not
  grant room access either.
- "Last room" memory only helps routing; it never grants access.
- Broken password hashes in the database are rejected as a wrong password. An
  admin password reset fixes them.

## Security requirements for hosting

- Host the app on its own origin. Cookies are host-only and cover the whole
  site.
- The proxy must pass on the original `https` scheme and host, or cookie writes
  are rejected (see [deployment](deployment.md#https-and-proxy)).
- Never enable credentialed cross-origin CORS.

Design reasoning, implementation details and past test results are in
[background](background/home-screen-installation.md).

## Real-device acceptance checklist

Use HTTPS and disposable rooms, preferably on a spare device or profile. Record
OS and browser versions with the results. Do not remove a working icon just to
test.

1. **Fresh iPhone install:** in Safari, sign in to room A, then Add to Home
   Screen. The icon should open room A without a second sign-in; a password
   prompt counts as a failure. Repeat starting from an old localStorage login,
   and with browser storage disabled.
2. **Install from password page:** the icon opens room A but asks for the
   password.
3. **Restart:** close and reopen the app, and restart the server. Access still
   works. Change the password elsewhere; the app asks for it again without
   showing private data.
4. **Old icon:** install an icon on the old version first, then upgrade. Test
   with valid, missing and revoked access. Recovery still works; note whether
   the icon's address changes.
5. **Multiple rooms:** open A and B in tabs, install from A, check where it
   opens. Switch to B, close, reopen, note what happens. Try installing from B
   with A already installed.
6. **Other pages:** root, public list, admin and invitation pages use only the
   default manifest, with no room data or invitation tokens.
7. **Deleted room:** delete an installed disposable room and open its icon.
   Expect "Room not found".
8. **Android Chrome:** repeat fresh install, restart, old icon, multiple rooms
   and password revocation. Try both "Install" and "Add shortcut" if offered.

Results are tracked in the
[backlog](../plans/backlog.md#manual-checks).
