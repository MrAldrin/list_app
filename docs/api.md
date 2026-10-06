# JSON API (Svelte frontend)

The contract between the Python server and the Svelte app. It covers items and lists, room
management, share links, admin and creation invitations.

The business rules live in Python and are shared with every write path: see
[item writes](item-writes.md) and [checked-item visibility](checked-item-visibility.md).

## Basics

- Base path `/api/v1`. Requests and responses are JSON (`Content-Type:
  application/json`). Every response has `Cache-Control: no-store`.
- Lists and items are identified by `uid`, a UUID string. A `uid` is never
  reused. Integer IDs, password hashes and room tokens are never sent. Share
  tokens are sent only to room members, by the share-link endpoints.
- A room is identified by its `slug` (the same as in `/room/{slug}`).
- Every room request checks room access on the server, in the same transaction
  as the read or write.
- An unknown room and a room you cannot access give the same response.

## Errors

HTTP errors use one shape:

```json
{"error": {"code": "not_authenticated", "message": "Sign in to this room."}}
```

| Status | `code` | When |
|---|---|---|
| 400 | `invalid_request` | Body is not valid JSON |
| 405 | `invalid_request` | Known API path, wrong method (`Allow` header lists the right ones) |
| 413 | `invalid_request` | Body larger than 64 KB |
| 415 | `invalid_request` | Write without `Content-Type: application/json` |
| 422 | `invalid_request` | Body is not a JSON object, missing, unknown or wrong fields (types are strict: `"3"` is not a number), a number out of range, unknown op `type`, bad `since`, a client `uid` already used |
| 401 | `invalid_password` | `POST …/session`: wrong password **or** unknown room (identical); admin sign-in: wrong password |
| 401 | `admin_required` | Admin endpoint without admin sign-in |
| 401 | `not_authenticated` | No room cookie, revoked or expired token, or unknown room |
| 401 | `share_unavailable` | Share link: the token opens no list (never issued, reset, or the list was deleted; identical) |
| 403 | `forbidden_origin` | Write without a same-origin `Origin` header |
| 403 | `wrong_password` | Change password or delete room: wrong room password (you have access) |
| 404 | `not_found` | Unknown API path |
| 404 | `list_unavailable` | Share-link endpoints: the list is gone or in another room |
| 404 | `room_unavailable` | Admin password reset: no room has this slug |
| 404 | `invitation_unavailable` | Creation invitation: unknown, expired, revoked or deleted (identical) |
| 409 | `op_id_reused` | Same `op_id` sent again with a different body |
| 500 | `internal_error` | Unexpected server error (a bug); no details are sent |
| 503 | `unavailable` | Database busy or failing; retry later. Saved access stays. |

There is no rate limiting, also not for the admin password; the app has none today.

## Writes: same-origin rule

Every `POST` and `DELETE` must:

- send `Origin` equal to the server's own origin (scheme and host), and
  `Sec-Fetch-Site` either absent or `same-origin`. This reuses the check in
  `src/room_cookies.py`. CORS is never enabled.
- send a JSON body with `Content-Type: application/json` (`DELETE …/session`
  has no body).

`GET` requests change no data and need only the cookie. One exception is
housekeeping: listing invitations deletes old inactive ones.
`DELETE /api/v1/rooms/{slug}` has a JSON body.

## Room session

The room password gives a room token in an HTTP-only cookie. The browser never
stores the password, and JavaScript never sees the token.

| Request | Body | Success |
|---|---|---|
| `POST /api/v1/rooms/{slug}/session` | `{"password": "…"}` | 200 `{"room": {"slug", "name"}}`, sets the cookies |
| `GET /api/v1/rooms/{slug}/session` | – | 200 `{"room": {"slug", "name"}}` ("who am I") |
| `DELETE /api/v1/rooms/{slug}/session` | – | 204; revokes the token and clears the cookie, also when already signed out |
| `GET /api/v1/last-room` | – | 200 `{"slug": "home-ab12cd"}` or `{"slug": null}` |

Cookies (`SameSite=Lax`, `Path=/`, one year, `HttpOnly`):

- **HTTPS:** `__Host-listapp-room-<sha256(slug)>`
  and `__Host-listapp-last-room`, with `Secure`. Phones that signed in before
  the Svelte switch keep working: the cookies have the same names.
- **Plain HTTP** (local network tests): `listapp-room-<sha256(slug)>` and
  `listapp-last-room`, without `Secure`. Browsers refuse `__Host-` cookies
  without `Secure`. No localStorage fallback.

`GET …/session` with a revoked token returns 401 and clears the cookie. A
password change revokes all tokens of the room. If `DELETE …/session` cannot
revoke the token (503), it keeps the cookie so the client can retry. `last-room` is routing only: it
names the last room this browser signed in to, not whether access still works.

## Room management

Rename is an op (`room.rename`, below). Changing the password and deleting
the room need the room password, so they have their own endpoints: they are
not ops, are never stored and are not retry-safe. Both need room access (the
cookie) first; without it the answer is 401 `not_authenticated`, as for an
unknown room. The password is checked in the same transaction.

| Request | Body | Success |
|---|---|---|
| `POST /api/v1/rooms/{slug}/password` | `{"current_password", "new_password"}` | 200 `{"room": {"slug", "name"}}`, sets new cookies |
| `DELETE /api/v1/rooms/{slug}` | `{"password"}` | 204, clears the room cookie |

- **Change password:** a wrong current password is 403 `wrong_password`
  ("Incorrect current password"); nothing changes. A new password that is
  blank (only spaces) or longer than 72 bytes is 422 with a message. It is
  saved as typed. Every token of the room is revoked; this browser gets a new
  one in the cookie. Other devices must sign in again.
- **Delete room:** a wrong password is 403 `wrong_password` ("Incorrect
  password"). Deletes the room and all its lists and items; this cannot be
  undone. Clears the room cookie, and `last-room` when it names this room.
- Passwords are at most 1,024 characters (else 422).
- Open streams of the room are woken after the answer is sent: they send
  `revoked` to signed-out devices (live updates, below).

## Share links

A share link (`/share/{token}`) opens one list for viewing and editing
without the room password. The rules are in [public sharing](public-sharing.md).
The token is in the path; it is never a cookie, and it never gives room access.

Share holders:

| Request | Body | Success |
|---|---|---|
| `GET /api/v1/share/{token}/changes?since=N` | – | 200 feed of the one list (below) |
| `POST /api/v1/share/{token}/ops` | an op | 200, like `…/ops` of a room |
| `GET /api/v1/share/{token}/events` | – | the live stream, like a room's |

- The feed is always a full snapshot (`full: true`) of the list and its
  items, with `deletions: []` and the list's `slug` as `""`. `room` is `null`,
  except when the request's cookie for the list's room is valid at that moment:
  then it is `{"slug", "name"}` of that room, so the page can offer "back to
  room" and "Reset share link". A missing, stale or other room's cookie gives
  `null`, and no other part of a share answer names the room.
  `since` is checked (as for rooms) but not used. `seq` is the room's `seq`,
  the same number op answers and the stream send.
- Ops: the list ops `list.tag_add`, `list.tag_remove`, `list.visibility` and
  every item op. Other types (`room.rename`,
  `list.create`, `list.rename`, `list.delete`) are 422. A `list_uid` other
  than the shared list's is rejected as `list_unavailable`. Ops are stored per
  room, as for room ops, so retries are safe.
- The token is checked in the same transaction as each read and write. After a
  reset every request with the old token is 401 `share_unavailable`, also the
  retry of an op sent before. The stream sends `revoked` and closes.

Room members (need the room cookie; 401 `not_authenticated` without it):

| Request | Body | Success |
|---|---|---|
| `GET /api/v1/rooms/{slug}/lists/{list_uid}/share-link` | – | 200 `{"token": "…"}` |
| `POST /api/v1/rooms/{slug}/lists/{list_uid}/share-link` | `{}` | 200 `{"token": "…"}`: the new token |

- Reset gives the list a new token and the old link stops working for
  everyone. Room access and the list's room are checked in the same write
  transaction. It is not an op (the answer holds a token, which must not be
  stored for replays); a second reset does no harm.
- Changing the room password does not reset share links.

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
  cannot be empty"); the password must not be empty ("Password cannot be
  empty"), at most 72 bytes, and is saved as typed. Both give 422. Creating
  a room does not sign the admin in to it.
- **Password reset:** no current password needed. The new password follows
  the change-password rules above (422 when blank or longer than 72 bytes).
  Every token of the room is revoked and its streams are woken. A room that is
  gone is 404 `room_unavailable`.
- Passwords are at most 1,024 characters (else 422).

## Creation invitations

An invitation link (`/create-room/{token}`) lets anyone create a new room.
The rules are in [room invitations](room-invitations.md). Invitations never
give access to any room, also not to the room they create.

Admins (need admin sign-in; 401 `admin_required` first, as above):

| Request | Body | Success |
|---|---|---|
| `GET /api/v1/admin/invitations` | – | 200 `{"invitations": [invitation]}`, newest first |
| `POST /api/v1/admin/invitations` | `{}` | 200 `{"invitation", "token"}` |
| `POST /api/v1/admin/invitations/{id}/revoke` | `{}` | 200 `{}` |

```json
{"id": 3, "status": "active", "created_at": "2026-10-05T09:12:00Z",
 "expires_at": "2026-10-12T09:12:00Z", "revoked_at": null}
```

- `status` is `active`, `revoked` or `expired` (revoked wins). Times are UTC.
- An invitation is valid for 7 days and can be used many times.
- The token is only in the answer that issues it; only its sha256 is stored.
- Listing deletes invitations that have been inactive for 7 days.
- Revoking an unknown or already revoked invitation changes nothing. Rooms
  created with it keep working. `id` must be a whole number from 1 (else 422).

Anyone with the link (no sign-in):

| Request | Body | Success |
|---|---|---|
| `GET /api/v1/invitations/{token}` | – | 200 `{}` when it can create a room |
| `POST /api/v1/invitations/{token}/rooms` | `{"name", "password"}` | 200 `{"room": {"slug", "name"}}` |

- A link that cannot create a room is 404 `invitation_unavailable`, the same
  for every reason. The invitation is checked again in the write transaction.
- The name is trimmed and must have 1–100 characters. The password must not
  be blank, at most 72 bytes, and is saved as typed. Both give 422 with
  the usual message. Passwords are at most 1,024 characters in the body.
- No cookie is set: the creator signs in to the new room with its password.

## Data shapes

```json
{
  "room": {"slug": "home-ab12cd", "name": "Home"},
  "list": {
    "uid": "7c0e…", "slug": "groceries-1a2b3c", "name": "Groceries",
    "tags": ["Lidl", "Market"],
    "hide_done": {"mode": "age", "age_days": 7, "recent_count": 10},
    "changed_seq": 41
  },
  "item": {
    "uid": "c39f…", "list_uid": "7c0e…", "name": "milk",
    "done": true, "completed_at": "2026-10-03T09:12:44.123456Z",
    "quantity": 2, "description": "lactose free", "tags": ["Lidl"],
    "changed_seq": 44
  }
}
```

- List `name` is shown as typed. Item `name` is stored in lowercase.
- List `tags` are sorted ignoring case. Item `tags` keep their order.
- `hide_done.mode` is `off`, `all`, `age` or `recent`; counts are 1–100,000.
- `completed_at` is UTC, or `null` when not done or not known (items checked
  before completion times existed).
- `changed_seq` is the room `seq` of the row's last change.
- The client sorts items itself (open first, then by name). It computes hidden
  items with the rules in [checked-item visibility](checked-item-visibility.md).
  In `recent` mode, items without `completed_at` rank last in no fixed order;
  the API does not expose creation order.

## Reading: the changes feed

`GET /api/v1/rooms/{slug}/changes?since=N` is the only read path for room data.
Each room has a counter `seq`; every write in the room increases it.

```json
{
  "seq": 44,
  "full": false,
  "room": {"slug": "home-ab12cd", "name": "Home"},
  "lists": ["…lists changed after N…"],
  "items": ["…items changed after N…"],
  "deletions": [{"kind": "item", "uid": "a1b2…"}, {"kind": "list", "uid": "9f8e…"}]
}
```

- `since=0` returns a **full snapshot** (`full: true`): every list and item,
  no deletions. The client replaces all its data for the room.
- The server also sends a full snapshot when it cannot serve the delta: `since`
  is larger than the current `seq` (for example after a database restore), or
  older than the deletion records it keeps. Deletion records are not pruned
  yet, so for now only the first case happens.
- `since` is required: a whole number from 0 up; anything else gives 422.
- Stored values are read leniently: a missing quantity is 1,
  a missing description is `""`, unreadable tags are `[]`, and an unreadable
  `completed_at` is `null`.
- Otherwise (`full: false`) the client upserts `lists` and `items` by `uid` and
  removes each `uid` in `deletions`.
- A deleted list means its items are gone too. The client drops them, whether or
  not the feed also lists them.
- `room` is always included, so a room rename shows up.
- Store `seq` and send it as `since` next time.
- How the server tracks changes: [change tracking](change-tracking.md).

## Writing: operations

All writes go to one endpoint, `POST /api/v1/rooms/{slug}/ops`, one operation
per request. Each operation says what the user did (intent), not the full new
value.

```json
{"op_id": "5d1e…", "type": "item.quantity_delta",
 "list_uid": "7c0e…", "item_uid": "c39f…", "delta": 1}
```

Responses (HTTP 200), one applied and one rejected:

```json
{"op_id": "5d1e…", "status": "applied", "result": {}, "seq": 45}
{"op_id": "6a2f…", "status": "rejected", "code": "duplicate_active",
 "message": "'milk' is already on the list", "seq": 45}
```

- `op_id` is a UUID made by the client, one per user action.
- `applied`: the change is saved. `seq` is the room's `seq` after it.
- `rejected`: a business rule said no; nothing changed. `seq` is the current
  `seq`. Show `message` to the user.
- **Retry-safe.** Applied and rejected results are stored for at least 30
  days. Sending the same `op_id` with the same body returns the stored response
  unchanged. The same `op_id` with a different body, or for another room,
  gives 409 `op_id_reused`. "Same body" means the same fields and values after
  checking: key order, UUID letter case and an optional field sent as `null`
  do not count. Results older than 30 days are removed when the server starts.
- HTTP errors (401, 403, 422, 503, …) are **not** stored. Fix the cause and
  retry with the same `op_id`.
- The client reads the changes feed to get the new data.

### Operation types

All item operations take `list_uid` and `item_uid`. Names are trimmed; item
names are lowercased.

| `type` | Fields | Result / notes |
|---|---|---|
| `room.rename` | `name` | Trimmed, case kept. Room names need not be unique. The new name shows in the feed's `room`. |
| `list.create` | `name`, `uid`? | `{"list_uid", "slug", "created"}`. If a list with that name exists (ignoring case), it is returned with `created: false` and the client `uid` is not used. |
| `list.rename` | `list_uid`, `name`, `base_seq` | – |
| `list.delete` | `list_uid` | Deletes the list and all its items. |
| `list.tag_add` | `list_uid`, `tag` | Adds one tag (trimmed); no change if it exists. Tags match exactly, case included. Also used to undo a tag delete. |
| `list.tag_remove` | `list_uid`, `tag` | Removes one tag (exact match) from the list; no change if it is not there. Item tags are not changed. |
| `list.visibility` | `list_uid`, `mode`?, `age_days`?, `recent_count`? | Sends only the changed fields (at least one); the server keeps the others. Out-of-range values give 422. |
| `item.add` | `list_uid`, `name`, `uid`? | `{"item_uid", "outcome"}`, outcome `added` or `restored`. Add-or-restore: a new item, or an existing checked item is unchecked (its own `uid` is returned). |
| `item.set_done` | `list_uid`, `item_uid`, `done` | Sets the state. Checking an already checked item keeps its `completed_at`. |
| `item.quantity_delta` | `list_uid`, `item_uid`, `delta` | Adds `delta` to the stored quantity; never below 1. |
| `item.edit` | `list_uid`, `item_uid`, `name`, `description`, `quantity`?, `base_seq` | Saves all fields together or none. `quantity` absent or `null` keeps it; below 1 saves 1. The description is trimmed. |
| `item.toggle_tag` | `list_uid`, `item_uid`, `tag` | Toggles one tag on the stored item tags. |
| `item.delete` | `list_uid`, `item_uid` | Applied also when the item is already gone. |
| `item.restore` | `list_uid`, `uid`?, `name`, `done`, `tags`, `description`, `quantity`, `completed_at` | Undo of a delete, with the data the client kept. Creates a new item with a new `uid`: `{"item_uid"}`. `completed_at` (a time or `null`) is kept only when `done`, and saved as UTC. |

`?` means optional. A client `uid` must be a UUID that was never used by any
list or item, in any room, even a deleted one; if it was, the server answers
422. `quantity` and `delta` are whole numbers from −1,000,000 to 1,000,000.
`completed_at` is an ISO 8601 time; without a time zone it counts as UTC.

`base_seq` is the `changed_seq` the edit was based on. It is required but not
yet used: for now **the last write wins**. Conflict rules come in Milestone 6.

### Rejection codes

| `code` | Operations | Message |
|---|---|---|
| `invalid_name` | `room.rename`, `list.create`, `list.rename`, `list.tag_add`, `item.add`, `item.edit`, `item.restore` | Name cannot be empty |
| `duplicate_name` | `list.rename`, `item.edit` | 'X' already exists (in this room) |
| `duplicate_active` | `item.add` | 'x' is already on the list |
| `undo_name_taken` | `item.restore` | Cannot undo: item name already exists |
| `list_unavailable` | every op with `list_uid` | The list is no longer available. |
| `item_not_found` | `item.set_done`, `item.quantity_delta`, `item.edit`, `item.toggle_tag` | The item is no longer available. |

A list in another room counts as `list_unavailable`, like a deleted one. An
item in another list counts as `item_not_found` (`item.delete`: applied, no
change).

## Live updates

`GET /api/v1/rooms/{slug}/events` is a Server-Sent Events stream. It only says
that something changed; the client then reads the changes feed.

```
event: seq
data: {"seq": 45}

: keep-alive

event: revoked
data: {}
```

- `seq` is sent once on connect and after each write in the room. It is sent only when the room `seq` changed, so the same value never
  comes twice in a row.
- A keep-alive comment is sent about every 15 seconds.
- Access and `seq` are checked again on every message, keep-alives included.
  When access is gone, the server sends `revoked` and closes the stream. The
  client then calls `GET …/session` and shows the sign-in prompt on 401.
- Without access at connect time, the response is the 401 JSON error.
- Headers: `Content-Type: text/event-stream`, `Cache-Control: no-store`,
  `X-Accel-Buffering: no` (no proxy buffering).
- The server closes the stream when it shuts down or restarts (after at most
  `SHUTDOWN_TIMEOUT_SECONDS` in `src/server.py`), and when the database is
  unavailable.
- On a dropped connection the client reconnects and reads the changes feed.
