# API: Admin

Part of the [JSON API](api.md). Admin sign-in and admin room tools.

## Admin

The admin password is `APP_PASSWORD`. Admin sign-in has its own cookie, like
the room cookie: `__Host-listapp-admin` on HTTPS (`Secure`, Path `/`, no
Domain), `listapp-admin` on plain HTTP (local network testing). Both are
HTTP-only and `SameSite=Lax`, and last 14 days. The value is a signed token
(`v1.<expiry>.<nonce>.<signature>`); the signature uses a key made from the
current `APP_PASSWORD`, so **changing `APP_PASSWORD` ends every admin
session**. Nothing is stored on the server, so signing out clears the cookie
in this browser only. Admin sign-in never gives room access: the
room endpoints ignore it, and admin endpoints never set a room cookie.

| Request | Body | Success |
|---|---|---|
| `POST /api/v1/admin/session` | `{"password"}` | 200 `{}` and the admin cookie |
| `GET /api/v1/admin/session` | – | 200 `{}` when this browser is signed in as admin; 401 `admin_required` otherwise (and a useless cookie is cleared) |
| `DELETE /api/v1/admin/session` | – | 204 and the cookie is cleared, also when not signed in |
| `GET /api/v1/admin/rooms` | – | 200 `{"rooms": [{"slug", "name"}]}` |
| `POST /api/v1/admin/rooms` | `{"name", "password"}` | 200 `{"room": {"slug", "name"}}` |
| `POST /api/v1/admin/rooms/{slug}/password` | `{"new_password"}` | 200 `{}` |
| `DELETE /api/v1/admin/rooms/{slug}` | – | 204 |

- **Sign-in:** a wrong password is 401 `invalid_password` ("Wrong password").
  It does not sign out an admin who is signed in. The check is exact and in
  constant time, as is the cookie signature check.
- **Status:** `GET /api/v1/admin/session` is how the app learns that this
  browser is signed in as admin (for "Back to admin" on the room page).
- Writes need the same-origin check, sign-in and sign-out included.
- Every other admin endpoint is 401 `admin_required` without admin sign-in,
  checked before the body or the room.
- **Rooms:** every room, by name ignoring case.
- **Create room:** the name is trimmed and must not be empty ("Room name
  cannot be empty"). The password follows the [room password rule](api-rooms.md#room-password-rule).
  Both give 422. Creating a room does not sign the admin in to it.
- **Password reset:** no current password needed. The new password follows
  the [room password rule](api-rooms.md#room-password-rule).
  Every token of the room is revoked and its streams are woken. A room that is
  gone is 404 `room_unavailable`.
- **Delete room:** no room password needed. Deletes the room with all its
  lists, items and tokens, as the [room's own delete](api-rooms.md#room-management) does.
  The answer clears this browser's room cookies for it. Its open streams are
  woken and send `revoked`. A room that is gone is 404 `room_unavailable`.
  Creation invitations are not room data and stay; see
  [creation invitations](api-sharing.md#creation-invitations).
- Passwords are at most 1,024 characters (else 422).
