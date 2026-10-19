# API: Rooms and sessions

Part of the [JSON API](api.md). Base path, IDs and error format are in the overview.

## Room session

The room password gives a room token in an HTTP-only cookie. The browser never
stores the password, and JavaScript never sees the token.

### Room password rule

Every path that sets a room password uses this rule: admin room creation,
admin password reset, room password change, and room creation from an
invitation. A password that is blank (only spaces), shorter than 4 characters,
or longer than 72 UTF-8 bytes is 422 `invalid_request`. The password is saved
as typed. Sign-in only compares the password and does not apply the rule, so
older, shorter passwords still open their rooms.

| Request | Body | Success |
|---|---|---|
| `POST /api/v1/rooms/{slug}/session` | `{"password": "…"}` | 200 `{"room": {"slug", "name"}}`, sets the cookies |
| `GET /api/v1/rooms/{slug}/session` | – | 200 `{"room": {"slug", "name"}}` ("who am I") |
| `DELETE /api/v1/rooms/{slug}/session` | – | 204; revokes the token and clears the cookie, also when already signed out |
| `GET /api/v1/last-room` | – | 200 `{"slug": "home-ab12cd"}` or `{"slug": null}` |

### Sign-in limit

Failed sign-ins are counted in memory, in this one process, for one minute.
Limits: 10 failures per room, 30 failures for all rooms together, and 10 failed
admin sign-ins for all clients. A room sign-in uses both room limits.
There is no per-client-address limit: Railway does not document a trustworthy
client address. A successful sign-in does not count. A full limit answers 429
`too_many_attempts` with `Retry-After` (seconds) before any password is checked.
Unknown rooms count the same way, so a 429 does not show whether a room exists.
Counts reset when the app restarts.

Cookies (`SameSite=Lax`, `Path=/`, one year, `HttpOnly`):

- **HTTPS:** `__Host-listapp-room-<sha256(slug)>`
  and `__Host-listapp-last-room`, with `Secure`. Phones that signed in before
  the Svelte switch keep working: the cookies have the same names.
- **Plain HTTP** (local network tests): `listapp-room-<sha256(slug)>` and
  `listapp-last-room`, without `Secure`. Browsers refuse `__Host-` cookies
  without `Secure`. No localStorage fallback.

- **Rooms list (written by the page, not the API):** `listapp-rooms` holds a
  JSON array of up to 10 `{slug, name}` objects, newest first. It has no
  `__Host-` prefix and gets `Secure` on HTTPS only. It is not HttpOnly and
  holds no token. The page writes it when a room loads from the server, removes
  the room on sign-out or after an admin or own room delete, and deletes the
  cookie when the list is empty. It only fills the Rooms panel under the room
  name; opening a room still needs its password or token.

`GET …/session` with a revoked token returns 401 and clears the cookie. A
password change revokes all tokens of the room. A room keeps its 200 newest
tokens; a new sign-in drops the oldest. If `DELETE …/session` cannot
revoke the token (503), it keeps the cookie so the client can retry. `last-room` is routing only: it
names the last room this browser signed in to, not whether access still works.

## Room management

Rename is an op (`room.rename`,
see [operation types](api-lists-items.md#operation-types)). Changing the password
and deleting the room need the room password, so they have their own endpoints: they are
not ops, are never stored and are not retry-safe. Both need room access (the cookie)
first; without it the answer is 401 `not_authenticated`, as for an unknown room. The
password is checked outside the database lock; the change is then written only if the
room has not changed meanwhile.

| Request | Body | Success |
|---|---|---|
| `POST /api/v1/rooms/{slug}/password` | `{"current_password", "new_password"}` | 200 `{"room": {"slug", "name"}}`, sets new cookies |
| `DELETE /api/v1/rooms/{slug}` | `{"password"}` | 204, clears the room cookie |

- **Change password:** a wrong current password is 403 `wrong_password`
  ("Incorrect current password"); nothing changes. A new password that breaks
  the [room password rule](#room-password-rule) is 422. Every token of the room
  is revoked; this browser gets a new one in the cookie. Other devices must
  sign in again.
- **Delete room:** a wrong password is 403 `wrong_password` ("Incorrect
  password"). Deletes the room and all its lists and items; this cannot be
  undone. Clears the room cookie, and `last-room` when it names this room.
- Request password fields are at most 1,024 characters (else 422). This is the
  request-field limit. The 4-character minimum and 72-byte maximum in the
  [room password rule](#room-password-rule) apply only when setting a password.
- Open streams of the room are woken after the answer is sent: they send
  `revoked` to signed-out devices (see [live updates](api-sync.md#live-updates)).
