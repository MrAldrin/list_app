# API: Reading and live updates

Part of the [JSON API](api.md). This page describes the changes feed and the live update stream.

## Reading: the changes feed

`GET /api/v1/rooms/{slug}/changes?since=N` is the only read path for room data.
Each room has a counter called `seq`. Every write in the room increases it.

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

- When `since=0`, the server returns a **full snapshot** (`full: true`). It
  includes every list and item, with no deletions. The client replaces all its
  data for the room.
- The server also returns a full snapshot when it cannot serve a delta. This
  happens when `since` is larger than the current `seq` (for example, after a
  database restore) or lower than the newest pruned deletion record. The server
  keeps deletion records for 90 days.
- `since` is required. It must be a whole number from 0 up. Any other value
  gives 422.
- The server reads stored values leniently. A missing quantity is 1, and a
  missing description is `""`. Unreadable tags are `[]`, and an unreadable
  `completed_at` is `null`.
- `date` is `YYYY-MM-DD` or `null` when there is no date. `add_count` is at
  least 1; a missing value reads as 1. `added_at` is a UTC time or `null` for
  items from before counting.
- When `full: false`, the client upserts the `lists` and `items` entries by
  `uid`. It removes each `uid` in `deletions`.
- When a list is deleted, its items are gone too. The client drops those items,
  whether or not the feed also lists them.
- The feed always includes `room`, so the client receives room renames.
- Store `seq` as the room's change cursor. Send it as `since` next time.
- See [change tracking](change-tracking.md) for how the server tracks changes.

## Live updates

`GET /api/v1/rooms/{slug}/events` opens a Server-Sent Events stream. The stream
only reports that something changed. The client then reads the changes feed.

```
event: seq
data: {"seq": 45}

: ping

event: revoked
data: {}
```

- The server sends `seq` when the client connects and after each room write.
  It sends it only when the room's `seq` changes. Therefore, the same value
  never appears twice in a row.
- The server sends a `: ping` comment about every 15 seconds when it sends
  nothing else.
- The server checks access and `seq` on each room write and at least every 15
  seconds. When access is gone, the server sends `revoked` and closes the
  stream. The client then calls `GET …/session` and shows the sign-in prompt on
  401.
- Without access when the client connects, the server returns a 401 JSON error.
- The server allows 100 open streams at once. When all are in use, a new stream
  gets the 503 `unavailable` JSON error. The client retries later.
- The response headers are `Content-Type: text/event-stream`,
  `Cache-Control: no-store`, and `X-Accel-Buffering: no` (no proxy buffering).
- The server closes the stream when it shuts down or restarts. It waits at most
  `SHUTDOWN_TIMEOUT_SECONDS` in `src/server.py`. The server also closes the
  stream when the database is unavailable.
- When a connection drops, the client reconnects and reads the changes feed.
