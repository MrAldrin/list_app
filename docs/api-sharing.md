# API: Sharing and invitations

Part of the [JSON API](api.md). Share links and creation invitations.

## Share links

A share link (`/share/{token}`) opens one list for viewing and editing
without the room password. The rules are in [public sharing](public-sharing.md).
The token is in the path; it is never a cookie, and it never gives room access.

Share holders:

| Request | Body | Success |
|---|---|---|
| `GET /api/v1/share/{token}/changes?since=N` | – | 200 feed of the one list (below) |
| `POST /api/v1/share/{token}/ops` | an op | 200, like `…/ops` of a room |
| `GET /api/v1/share/{token}/events` | – | the live stream, like a room's, but `seq` is sent only when the list's seq changes |

- The feed is always a full snapshot (`full: true`) of the list and its
  items, with `deletions: []` and the list's `slug` as `""`. `room` is `null`,
  except when the request's cookie for the list's room is valid at that moment:
  then it is `{"slug", "name"}` of that room, so the page can offer "back to
  room" and "Reset share link". A missing, stale or other room's cookie gives
  `null`, and no other part of a share answer names the room.
  `since` is checked (as for rooms) but not used. `seq` is the list's own seq,
  not the room's: it moves with changes to this list (its row, items and their
  deletions), not with other lists. Op answers of the link and its stream send
  the same number, so `seq` of a share op answer is the next feed `seq` if
  nothing else changed the list. How it is kept: [change tracking](change-tracking.md).
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

## Creation invitations

An invitation link (`/create-room/{token}`) lets anyone create a new room.
The rules are in [room invitations](room-invitations.md). Invitations never
give access to any room, also not to the room they create.

Admins (need admin sign-in; 401 `admin_required` first, as in [admin](api-admin.md)):

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
- An invitation is valid for 7 days and can create up to 5 rooms.
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
  for every reason (including the 5-room limit). The invitation is checked
  again in the write transaction, which also counts the new room.
- The name is trimmed and must have 1–100 characters. The password follows
  the [room password rule](api-rooms.md#room-password-rule). Both give 422 with a message.
  Passwords are at most 1,024 characters in the body.
- No cookie is set: the creator signs in to the new room with its password.
