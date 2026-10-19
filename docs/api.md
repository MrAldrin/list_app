# JSON API (Svelte frontend)

The contract between the Python server and the Svelte app. The reference is split
by area; the table below lists the parts. This page holds what every area shares.

Write rules live in Python and apply to every write path: see
[item writes](item-writes.md). The client applies checked-item visibility: see
[checked-item visibility](checked-item-visibility.md).

## Parts

| Area | File | Covers |
|---|---|---|
| Rooms and sessions | [api-rooms.md](api-rooms.md) | Room password, sign-in limit, cookies, changing or deleting a room |
| Sharing and invitations | [api-sharing.md](api-sharing.md) | Share links, creation invitations |
| Admin | [api-admin.md](api-admin.md) | Admin sign-in, admin room tools |
| Lists and items | [api-lists-items.md](api-lists-items.md) | Data shapes, write operations, conflicts, rejection codes |
| Reading and live updates | [api-sync.md](api-sync.md) | Changes feed, live update stream |

## Basics

- Base path `/api/v1`. Requests and responses are JSON (`Content-Type:
  application/json`). Every response has `Cache-Control: no-store` and an
  `X-Api-Version` header (see [API version](#api-version)).
- Lists and items are identified by `uid`, a UUID string. A `uid` is never
  reused. Integer IDs, password hashes and room tokens are never sent. Share
  tokens are sent only to room members, by the share-link endpoints.
- A room is identified by its `slug` (the same as in `/room/{slug}`).
- Every room request checks room access on the server, in the same transaction
  as the read or write.
- An unknown room and a room you cannot access give the same response.

## Auth model

Only the room password gives room access. Share links, admin sign-in and
creation invitations never do.

- **Room password:** gives a room cookie. Rules: [rooms and sessions](api-rooms.md).
- **Share link:** a token in the path opens one list. It is never a cookie:
  [share links](api-sharing.md#share-links).
- **Admin password:** gives an admin cookie for admin endpoints: [admin](api-admin.md).
- **Invitation link:** lets anyone create a room:
  [creation invitations](api-sharing.md#creation-invitations).

## Security headers

Every response, API or page, sends `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY` and `Content-Security-Policy: frame-ancestors 'none'`,
so no other site can frame the app. Code: `src/security_headers.py`. There is
no full Content-Security-Policy yet: the app shell has an inline theme script.

## API version

`API_VERSION` in `src/api/version.py` is a whole number set by hand. The server
sends it as `X-Api-Version` on every `/api` answer. The frontend keeps the
number it was built for as `EXPECTED_API_VERSION` in
`frontend/src/lib/data/compat.svelte.ts`. A test checks that both are equal.

- Bump both together in a change that would break a frontend that is still open
  in a browser: a changed meaning, a removed or renamed field, a new rule for
  writes. Adding a field or an endpoint needs no bump.
- A page that sees another number blocks writes and shows a Reload banner (see
  [offline viewing](offline-viewing.md#after-a-deploy)). A missing or unreadable
  header counts as compatible.

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
| 404 | `room_unavailable` | Admin password reset or delete: no room has this slug |
| 404 | `invitation_unavailable` | Creation invitation: unknown, expired, revoked, deleted or at its 5-room limit (identical) |
| 409 | `op_id_reused` | Same `op_id` sent again with a different body |
| 500 | `internal_error` | Unexpected server error (a bug); no details are sent |
| 429 | `too_many_attempts` | Too many failed sign-ins; `Retry-After` gives the seconds (see [sign-in limit](api-rooms.md#sign-in-limit)) |
| 503 | `unavailable` | Database busy or failing; retry later. Saved access stays. |

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
