# JSON API (Svelte frontend)

The contract between the Python server and the Svelte app. It covers the
prototype (Milestones 1–2 of the [rewrite plan](../plans/svelte-frontend-rewrite.md)).
Room management, share links, admin and invitations come in Milestone 3 and
are added here when they are built.

The business rules are the same as in NiceGUI: see
[item writes](item-writes.md) and [checked-item visibility](checked-item-visibility.md).

## Basics

- Base path `/api/v1`. Requests and responses are JSON (`Content-Type:
  application/json`). Every response has `Cache-Control: no-store`.
- Lists and items are identified by `uid`, a UUID string. A `uid` is never
  reused. Integer IDs, password hashes, tokens and share tokens are never sent.
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
| 401 | `invalid_password` | `POST …/session`: wrong password **or** unknown room (identical) |
| 401 | `not_authenticated` | No room cookie, revoked or expired token, or unknown room |
| 403 | `forbidden_origin` | Write without a same-origin `Origin` header |
| 404 | `not_found` | Unknown API path |
| 409 | `op_id_reused` | Same `op_id` sent again with a different body |
| 500 | `internal_error` | Unexpected server error (a bug); no details are sent |
| 503 | `unavailable` | Database busy or failing; retry later. Saved access stays. |

There is no rate limiting; the app has none today.

## Writes: same-origin rule

Every `POST` and `DELETE` must:

- send `Origin` equal to the server's own origin (scheme and host), and
  `Sec-Fetch-Site` either absent or `same-origin`. This reuses the check in
  `src/room_cookies.py`. CORS is never enabled.
- send a JSON body with `Content-Type: application/json` (`DELETE …/session`
  has no body).

`GET` requests have no side effects and need only the cookie.

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

- **HTTPS:** the same cookies NiceGUI uses, `__Host-listapp-room-<sha256(slug)>`
  and `__Host-listapp-last-room`, with `Secure`. Signing in on one UI signs in
  the other.
- **Plain HTTP** (local network tests): `listapp-room-<sha256(slug)>` and
  `listapp-last-room`, without `Secure`. Browsers refuse `__Host-` cookies
  without `Secure`. No localStorage fallback.

`GET …/session` with a revoked token returns 401 and clears the cookie. A
password change revokes all tokens of the room. If `DELETE …/session` cannot
revoke the token (503), it keeps the cookie so the client can retry. Signing
out on HTTPS also signs NiceGUI out in that browser (same cookie). `last-room` is routing only: it
names the last room this browser signed in to, not whether access still works.

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
- `hide_done.mode` is `off`, `all`, `age` or `recent`; counts are 0–100,000.
- `completed_at` is UTC, or `null` when not done or not known (items checked
  before completion times existed).
- `changed_seq` is the room `seq` of the row's last change.
- The client sorts items itself (open first, then by name). It computes hidden
  items with the rules in [checked-item visibility](checked-item-visibility.md).
  In `recent` mode, items without `completed_at` rank last in no fixed order;
  NiceGUI uses creation order, which the API does not expose.

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
- Stored values are read the way NiceGUI reads them: a missing quantity is 1,
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
- The client reads the changes feed to get the new data. Open NiceGUI pages
  refresh after each applied op.

### Operation types

All item operations take `list_uid` and `item_uid`. Names are trimmed; item
names are lowercased.

| `type` | Fields | Result / notes |
|---|---|---|
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

| `code` | Operations | Message (as in NiceGUI) |
|---|---|---|
| `invalid_name` | `list.create`, `list.rename`, `list.tag_add`, `item.add`, `item.edit`, `item.restore` | Name cannot be empty |
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

- `seq` is sent once on connect and after each write in the room, from either
  UI.
- A keep-alive comment is sent about every 15 seconds.
- Access is checked again on every message. When access is gone, the server
  sends `revoked` and closes the stream. The client then calls
  `GET …/session` and shows the sign-in prompt on 401.
- Without access at connect time, the response is the 401 JSON error.
- On a dropped connection the client reconnects and reads the changes feed.
