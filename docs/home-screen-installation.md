# Room-specific home-screen launch

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
- No cookies, database migrations, or authorization rules changed.

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

## Verification performed

- Full suite: **214 tests passed**; Ruff formatting and lint checks clean.
- Started a disposable real app server with a temporary database. Fetched the
  initial HTML for a room, room with `admin=true`, missing room, root, admin
  login, invalid invitation, and missing public list. Each contained exactly
  one correct manifest link; each linked manifest had the expected start URL
  and stable identity. No production/developer database was used.
- The suite reports the existing Starlette/httpx deprecation warning; no
  dependency changes were made for this feature.

## Outstanding real-device acceptance checklist

Use HTTPS and disposable rooms. Record OS/browser versions and results. These
checks have **not** been performed by the coding agent.

1. **Fresh iPhone installation:** in Safari, create/open room A, sign in, then
   Add to Home Screen. Launch the icon. Expect room A, possibly its password
   prompt, rather than a request to paste a room link. Sign in and verify lists.
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
