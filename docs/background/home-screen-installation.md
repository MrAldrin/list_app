# Home-screen installation: design and implementation notes

> Note: parts of this document describe the NiceGUI app, which was removed in the Svelte switch (step 4.3). Read those parts as history.

Supporting detail for [home-screen installation](../home-screen-installation.md).
That page is the source for current behavior.

## Why the root and admin routes stay separate

Older iOS installs opened an admin login page on every launch. Keeping `/` as a
public router (not the admin page) fixed that, and still lets older icons and
non-room pages recover the last remembered room. Admin tools stay at `/admin`
behind the global app password.

Room manifests only override `start_url`. Keeping `id: "/"` and `scope: "/"`
avoids duplicate installs and keeps navigation between room and list pages
inside the app. Separate per-room identities were rejected for that reason.

Cookies are copied into installed apps from iOS/iPadOS 17.2
([WebKit, Safari 17.2](https://webkit.org/blog/14787/webkit-features-in-safari-17-2/)).
Cookies are not assumed to stay in sync between Safari and the installed app
afterwards.

## Manifest implementation

`src/main.py` serves `/room-manifest/{slug}.json` from the same base manifest
as `/manifest.json` and `/static/manifest.json`. Room manifest responses are not
cacheable; unknown or deleted rooms return 404. Each page adds exactly one
manifest link per client, before any browser-storage awaits, so it is in the
initial page head.

## Tokens and authorization

`src/database_crud.py` checks bcrypt room-password hashes and issues opaque
random tokens. SQLite stores each token's hash, room ID and the room's
authorization version. A password change or reset increments the version and
deletes old tokens in the same transaction. Tokens survive server restarts.

`src/room_access.py` builds the private-page authorization context. Private
reads and writes validate the token against the database instead of trusting
the `authorized_rooms` UI cache. Admin login and `?admin=true` do not replace
room authorization.

Legacy localStorage key: `listapp_room_token_{slug}`. `listapp_last_room` and
the last-room cookie hold routing hints only. Passwords are never stored in the
browser.

## Cookie bridge

`src/room_cookies.py` exposes a POST-only token-to-cookie endpoint. A write
requires HTTPS, an exact matching Origin, a custom request header and a valid
token; cross-site Fetch Metadata is rejected. Cookie acceptance is confirmed
without returning credentials to JavaScript. Socket.IO accepts same-origin
handshakes only (instead of NiceGUI's wildcard default), for both websocket and
polling.

Known limits:

- The token briefly passes through JavaScript during login and migration, so
  this does not fully protect against malicious scripts on the app's own origin.
- Each remembered room adds a cookie. Fine for a few rooms, not hundreds.
- If the proxy reports the wrong scheme or host, cookie writes are rejected
  rather than weakening the checks. localStorage fallback may still work, but
  then sign-in is not carried into installed apps.

## Past verification (local, not production)

- Cookie implementation: 229 tests passed at the time, Ruff clean.
- Disposable HTTPS server with headless Chromium: sign-in, Secure/HttpOnly
  cookie creation, removal of migrated localStorage tokens, access from a fresh
  context with only copied cookies, legacy migration, fallback to the password
  after revocation, and HTTPS websockets with the same-origin rule.
- Room-launch implementation: 214 tests passed at the time, Ruff clean.
- A disposable server was checked for room, room with `admin=true`, missing
  room, root, admin login, invalid invitation and missing public list pages:
  each had exactly one correct manifest link with the expected start URL and
  identity.

Automated tests simulate copied cookies but not the operating system's Add to
Home Screen step. Real-device checks are in the
[acceptance checklist](../home-screen-installation.md#real-device-acceptance-checklist).
