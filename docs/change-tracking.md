# Change tracking

The database keeps track of every change to room data, so the
[changes feed](api.md#reading-the-changes-feed) can send only what changed.
SQLite triggers do the work (migration 4 in `src/database_setup.py`). They run
inside the writer's transaction, so every write path (NiceGUI, the API, share
links, admin) is covered, and a rolled-back write leaves no trace.

## What is stored

- `rooms.change_seq`: a counter per room. Every change in the room adds 1.
- `lists.uid`, `items.uid`: public IDs (UUID v4, lowercase). Never reused.
- `lists.changed_seq`, `items.changed_seq`: the room's `change_seq` right
  after the row's last change.
- `deletions`: one row per deleted list or item: `room_id`, `kind` (`list` or
  `item`), `uid`, `changed_seq`.
- `processed_ops`: stored API results per `op_id`, for retry-safe writes.
  Rows older than 30 days are deleted when the server starts.

Deleting a room removes its `deletions` and `processed_ops` rows
(`ON DELETE CASCADE`). Otherwise `deletions` rows are kept for now; pruning
them is decided with the offline work (Milestone 6 of the
[rewrite plan](../plans/svelte-frontend-rewrite.md)).

## What the triggers do

| Write | Effect |
|---|---|
| Insert a list or item | Bump the room, stamp `changed_seq`, fill `uid` if it is empty |
| Any update of a list or item | Bump the room, stamp `changed_seq` |
| Delete a list or item | Bump the room, add a `deletions` row |
| Rename a room | Bump the room |

- An item finds its room through its list. If the list is already gone, the
  item delete records nothing; clients drop the items of a deleted list.
- Deleting a list with items records each item, then the list.
- Password, token and room-creation writes do not bump. Resetting a share link
  does (it updates the list row); this is harmless, since the share token is
  never sent to clients.
- A write that matches no row (a stale item) changes nothing.

## Rules for code

- Never set `changed_seq` yourself. The update triggers skip a write that
  changes `changed_seq`; that is how they avoid looping.
- Do not turn on `PRAGMA recursive_triggers`. The guard above keeps the
  triggers safe even then, but nothing needs it.
- A client may insert its own `uid`; it must be a new UUID.
- **A migration that rebuilds `rooms`, `lists` or `items` drops these
  triggers.** It must create them again, and keep the `uid` and `changed_seq`
  columns and the `uid` indexes. Change the trigger definitions only in a new
  migration that drops and recreates them.
