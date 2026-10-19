# API: Reading and live updates

Part of the [JSON API](api.md). The changes feed and the live update stream.

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
  below the newest pruned deletion record. Deletion records are kept for 90
  days.
- `since` is required: a whole number from 0 up; anything else gives 422.
- Stored values are read leniently: a missing quantity is 1,
  a missing description is `""`, unreadable tags are `[]`, and an unreadable
  `completed_at` is `null`. `date` is `YYYY-MM-DD` or `null` (no date).
  `add_count` is at least 1 (a missing one reads as 1); `added_at` is a UTC
  time or `null` for items from before counting.
- Otherwise (`full: false`) the client upserts `lists` and `items` by `uid` and
  removes each `uid` in `deletions`.
- A deleted list means its items are gone too. The client drops them, whether or
  not the feed also lists them.
- `room` is always included, so a room rename shows up.
- Store `seq` and send it as `since` next time.
- How the server tracks changes: [change tracking](change-tracking.md).

## Live updates

`GET /api/v1/rooms/{slug}/events` is a Server-Sent Events stream. It only says
that something changed; the client then reads the changes feed.

```
event: seq
data: {"seq": 45}

: ping

event: revoked
data: {}
```

- `seq` is sent once on connect and after each write in the room. It is sent
  only when the room `seq` changed, so the same value never comes twice in a row.
- A `: ping` comment is sent about every 15 seconds while nothing else is sent.
- Access and `seq` are checked on every write in the room and at least every
  15 seconds. When access is gone, the server sends `revoked` and closes the
  stream. The client then calls `GET …/session` and shows the sign-in prompt on
  401.
- Without access at connect time, the response is the 401 JSON error.
- The server allows 100 open streams at once. When full, a new stream gets the
  503 `unavailable` JSON error; the client retries later.
- Headers: `Content-Type: text/event-stream`, `Cache-Control: no-store`,
  `X-Accel-Buffering: no` (no proxy buffering).
- The server closes the stream when it shuts down or restarts (after at most
  `SHUTDOWN_TIMEOUT_SECONDS` in `src/server.py`), and when the database is
  unavailable.
- On a dropped connection the client reconnects and reads the changes feed.
