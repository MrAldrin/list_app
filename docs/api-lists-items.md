# API: Lists and items

Part of the [JSON API](api.md). Data shapes and write operations.

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
    "quantity": 2, "description": "lactose free", "date": "2026-10-18",
    "tags": ["Lidl"], "add_count": 2, "added_at": "2026-10-18T08:30:00.000Z",
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
  do not count. Results older than 30 days are removed when the server starts and once a day.
- HTTP errors (401, 403, 422, 503, …) are **not** stored. Fix the cause and
  retry with the same `op_id`.
- The client reads the [changes feed](api-sync.md#reading-the-changes-feed) to get the new data.

### Operation types

All item operations take `list_uid` and `item_uid`. Names are trimmed; item
names are lowercased.

| `type` | Fields | Result / notes |
|---|---|---|
| `room.rename` | `name` | Trimmed, case kept. Room names need not be unique. The new name shows in the feed's `room`. |
| `list.create` | `name`, `uid`? | `{"list_uid", "slug", "created"}`. If a list with that name exists (ignoring case), it is returned with `created: false` and the client `uid` is not used. |
| `list.rename` | `list_uid`, `name`, `base_seq` | Checked against `base_seq` ([conflicts](#conflicts)). |
| `list.delete` | `list_uid` | Deletes the list and all its items. |
| `list.tag_add` | `list_uid`, `tag` | Adds one tag (trimmed); no change if it exists. Tags match exactly, case included. Also used to undo a tag delete. |
| `list.tag_remove` | `list_uid`, `tag` | Removes one tag (exact match) from the list; no change if it is not there. Item tags are not changed. |
| `list.visibility` | `list_uid`, `mode`?, `age_days`?, `recent_count`? | Sends only the changed fields (at least one); the server keeps the others. Out-of-range values give 422. |
| `item.add` | `list_uid`, `name`, `uid`? | `{"item_uid", "outcome", "changed_seq"}`, outcome `added` or `restored`. Add-or-restore: a new item, or an existing checked item is unchecked (its own `uid` is returned). Either one counts as an add: `add_count` +1 (a new item starts at 1) and `added_at` is now. |
| `item.set_done` | `list_uid`, `item_uid`, `done`, `base_seq`? | Sets the state. Checking an already checked item keeps its `completed_at`. Unchecking a checked item counts as an add (`add_count` +1, `added_at` now); checking, or unchecking an unchecked item, does not. Checked against `base_seq` if sent ([conflicts](#conflicts)). |
| `item.quantity_delta` | `list_uid`, `item_uid`, `delta` | Adds `delta` to the stored quantity; never below 1. |
| `item.edit` | `list_uid`, `item_uid`, `name`, `description`, `quantity`?, `date`?, `base_seq` | Saves all fields together or none. `quantity` absent or `null` keeps it; below 1 saves 1. `date` absent keeps it; `null` clears it. The description is trimmed. Checked against `base_seq` ([conflicts](#conflicts)). |
| `item.toggle_tag` | `list_uid`, `item_uid`, `tag`, `active`? | Toggles one tag on the stored item tags. With `active`, sets the tag on (`true`) or off (`false`); already in that state changes nothing, so the op is safe to send twice. |
| `item.delete` | `list_uid`, `item_uid` | Applied also when the item is already gone. |
| `item.restore` | `list_uid`, `uid`?, `name`, `done`, `tags`, `description`, `quantity`, `completed_at`, `date`?, `add_count`?, `added_at`? | Undo of a delete, with the data the client kept. Creates a new item with a new `uid`: `{"item_uid", "changed_seq"}`. `completed_at` (a time or `null`) is kept only when `done`, and saved as UTC. `date` is kept as sent (absent is no date). `add_count` and `added_at` are kept as sent (absent: 1 and no time); an undo is not an add. |

`?` means optional. A client `uid` must be a UUID that was never used by any
list or item, in any room, even a deleted one; if it was, the server answers
422. `quantity` and `delta` are whole numbers from −1,000,000 to 1,000,000.
`completed_at` is an ISO 8601 time; without a time zone it counts as UTC.
`date` is a real calendar day as `YYYY-MM-DD`; anything else is a 422.
`add_count` is a whole number from 1 up; `added_at` is a readable time.

### Conflicts

`base_seq` is the row's `changed_seq` that the page had when the user acted.
It is required for `list.rename` and `item.edit`, and optional for
`item.set_done`. Without it the last write wins.

If the row changed after `base_seq` and the stored value differs from what the
op wants, the op is rejected with `changed_meanwhile` and nothing changes. What
the op wants:

- `item.edit`: name, description, quantity and date (quantity and date only if sent).
- `item.set_done`: the done state.
- `list.rename`: the name.

If the stored value already matches, the op is applied. A quantity that was
not sent is not compared.

Applied answers of one-row ops (`item.set_done`, `item.quantity_delta`,
`item.edit`, `item.toggle_tag`, `item.add`, `item.restore`, `list.rename`,
`list.tag_add`, `list.tag_remove`, `list.visibility`) include the row's new
`changed_seq` in `result`. A client can use it as the next `base_seq` for that
row. Answers stored before this was added have no `changed_seq`.

### Rejection codes

| `code` | Operations | Message |
|---|---|---|
| `invalid_name` | `room.rename`, `list.create`, `list.rename`, `list.tag_add`, `item.add`, `item.edit`, `item.restore` | Name cannot be empty |
| `too_long` | the same, after trimming: names 100 characters, `list.tag_add` tags 30, `item.edit` and `item.restore` descriptions 1000 | Name (Tag, Description) can be at most N characters |
| `too_many` | `item.add`, `item.restore` (1000 items per list); `list.create` (100 lists per room); `list.tag_add` (50 tags per list) | A list can have at most 1000 items; A room can have at most 100 lists; A list can have at most 50 tags |
| `duplicate_name` | `list.rename`, `item.edit` | 'X' already exists (in this room) |
| `duplicate_active` | `item.add` | 'x' is already on the list. Also has `item_uid`: the uid of the existing item. |
| `changed_meanwhile` | `list.rename`, `item.set_done`, `item.edit` | Someone else changed this meanwhile. |
| `undo_name_taken` | `item.restore` | Cannot undo: item name already exists |
| `list_unavailable` | every op with `list_uid` | The list is no longer available. |
| `item_not_found` | `item.set_done`, `item.quantity_delta`, `item.edit`, `item.toggle_tag` | The item is no longer available. |

A list in another room counts as `list_unavailable`, like a deleted one. An
item in another list counts as `item_not_found` (`item.delete`: applied, no
change).
