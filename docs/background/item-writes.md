# Item writes: implementation notes and test scope

> Note: parts of this document describe the NiceGUI app, which was removed in the Svelte switch (step 4.3). Read those parts as history.

Supporting detail for [item writes and stale pages](../item-writes.md). That
page is the source for current behavior. The audit that produced these fixes is
the [write atomicity audit](../../plans/write-atomicity-audit.md).

## Implementation notes

- Tag helpers read and update the stored array under `_DB_LOCK` and
  `BEGIN IMMEDIATE`, after validating the page identity. Two stale pages can
  toggle different tags without undoing each other.
- The full-array setters `update_item_active_tags` and
  `update_list_tags_settings` still exist for callers that really want to
  replace the whole array. The UI no longer uses them for quick actions.
- `rename_item_with_checks` validates `expected_slug` before checking for
  duplicates, so a stale page cannot decide anything about a new list that
  reused its ID. If another write takes the name first, it returns the
  duplicate-name status instead of raising a SQLite error.
- The token-authorized list rename is a separate path; it validates the room
  token and list ownership in its own write transaction.
- `update_room_password` checks the room ID and slug inside `BEGIN IMMEDIATE`
  before changing the password or deleting access tokens, and returns `False`
  on a mismatch. Password hashing happens outside the transaction. ID-only calls
  remain supported for non-UI callers.
- `create_list`, `create_room`, `rename_room` and `revoke_room_access_token`
  roll back and re-raise when the SQL write or commit fails. A failed token
  revocation leaves the token active. This covers failure cleanup for these
  entry points only; it does not make every multi-step edit atomic.
- The `expected_slug` argument is optional for other callers; a numeric ID alone
  is not the stale-page safeguard.
- Undo creates a new item ID; the original ID is not reserved.

## Test scope

- Tag tests cover concurrent distinct adds, a delete interleaved with an add,
  undo interleaving, UI feedback, stale-list rejection and recovery from an
  injected SQL failure.
- Failure tests inject `RAISE(ABORT)` and check unchanged rows, a closed
  transaction and a later successful write.
- `tests/test_write_atomicity_cross_path.py` runs room-token list creation,
  private and public writes, rejected authorization and duplicate names, then
  successful writes. Rejections leave data unchanged with no open transaction;
  successful writes keep room access, list slug, share token, tags,
  descriptions and quantities.
- `tests/test_api_concurrency.py` runs two API clients on one room: stale
  writes on a deleted item or list, renames, a duplicate-add race, parallel
  quantity deltas, undo after a re-add, and API writes mixed with NiceGUI
  writes from threads. Each client's copy built from the changes feed must
  equal a full load and the database.
- The cross-path test does not simulate browser callbacks. None of these tests
  prove every write path, real-device behavior or production concurrency.

## Item-ID reuse

A stale quick-tag callback was reproduced changing a newly created replacement
item after the old highest-ID item was deleted. The `toggle_tag`, `toggle`,
`change_qty`, `save` and `delete` callbacks in `src/main.py` all keep a numeric
item ID. The atomic tag and edit checks above do not fix this.
