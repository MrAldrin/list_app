# Remaining write atomicity review

Goal: prevent stale decisions and partial writes in the existing single-instance NiceGUI + SQLite app. This is a **plan**, not evidence of defects or completed fixes. Keep each fix small and independently testable; do not change the architecture or add a database framework. Refer to [current item-write behavior](../docs/item-writes.md) and [architecture](../ARCHITECTURE.md).

## Ground rules for every follow-up agent

1. Re-read the relevant source and tests; verify call sites (including UI callbacks), authorization and expected-slug handling before editing. Record a concrete interleaving or failure path, or mark the candidate safe with reasoning. A read followed by a write is not automatically a bug.
2. Reproduce risks with deterministic tests: coordinate two calls with events and separate SQLite connections where needed (the module lock serializes threads in one process), or inject an SQL failure using a temporary trigger. Assert both database state and return status/exception; ensure `db.in_transaction` is false after rejection/failure and the next valid write works. Do not use timing-only race tests or real production data.
3. Apply the smallest fix: put a decision and its mutation in one `BEGIN IMMEDIATE` write transaction under `_DB_LOCK`, or use a conditional SQL write plus row-count check where appropriate. Roll back every failure/early exit; preserve existing public API, auth checks, list identity, duplicate semantics and UI feedback. Do not add transactions around slow UI or network work.
4. For each chunk run `uv run ruff format .`, `uv run ruff check --fix .`, `uv run pytest -q`, then `uv run ruff format --check .` and `uv run ruff check .`. Update the relevant `docs/` behavior reference and the progress section below only for verified work. Use the repository's `jj` workflow; leave unrelated changes alone.

## Ordered chunks

1. **Inventory and classify.** Search `src/item_service.py`, `src/database_crud.py`, `src/room_invitations.py` and write callbacks in `src/main.py` for read/check/write and multiple commits. Trace UI paths to their actual DB helper; identify already-transactional paths and rank remaining risks. Current known covered cases include add/restore, item details, list-token operations, invitation room creation, password/token changes, deletion and undo. Deliver a short table of candidate, concrete risk (or safe reason), and proposed test; do not rewrite protected paths without evidence.
2. **Item rename duplicate check.** `item_service.rename_item_with_checks` calls `find_duplicate_name` before `rename_item`; the latter checks list identity in a transaction but does not repeat the duplicate check. Verify whether the unique index prevents corruption but turns the expected duplicate status into an `IntegrityError`, and whether a deleted/reused list can yield a stale duplicate decision. Add a deterministic competing-write test, then move the decision into the write transaction or reuse the atomic details-update helper without changing intended status/fields. Cover normal rename, duplicates, and stale list identity.
3. **List rename duplicate check.** `item_service.rename_list_with_checks` calls `find_list_by_name` before `rename_list`; compare the private helper's callers with `rename_list_with_room_token` (already checks token, ownership and duplicates in one transaction). Reproduce an intervening rename/create if possible. Make the private path return the intended duplicate result rather than leaking an integrity error; preserve expected-slug protection and authorization boundaries. Test conflicts and no partial changes.
4. **Service read-after-delete decision.** `delete_list_and_items` deletes and then calls `get_lists` to choose a remaining list. Determine whether a concurrent room/list change can make the returned navigation target unavailable or outside the expected room. This is a post-write UI decision, not automatically an atomicity violation; test the actual behavior first. If it needs changing, keep the response consistent without holding a database transaction across UI rendering.
5. **Other write entry points.** Review ID-based `create_list`, `create_room`, `rename_room`, `revoke_room_access_token`, item/tag setters and invitation create/revoke for errors at commit, validation performed outside the DB lock, and caller assumptions. Single-statement writes may already be atomic in SQLite; only add rollback/transaction logic where a reproducible issue exists. Check whether ID-only helpers are reachable from untrusted UI; don't broaden access inadvertently. Track database schema/migration hardening separately in the backlog.
6. **Cross-path regression and documentation.** Re-run focused and full tests; check rejected writes leave no open transaction, and successful writes still preserve tokens, slugs, tags, quantities, and existing feedback. Update `docs/item-writes.md` (or relevant room/sharing guide) for verified behavior. Record any remaining risks in the backlog instead of calling the database fully stable. Production concurrency/device verification remains separate.

## Progress (update at the bottom as work completes)

- [x] Starting point: list deletion and both room deletion paths have rollback tests; see `tests/test_database_crud.py`. This predates this plan.
- [ ] Chunk 1: inventory/classification.
- [ ] Chunk 2: item rename.
- [ ] Chunk 3: list rename.
- [ ] Chunk 4: navigation after deletion.
- [ ] Chunk 5: remaining write entry points.
- [ ] Chunk 6: cross-path regression and current-reference updates.

Record each chunk's findings, tests run, and any deferred issues here; checking a box requires implementation **and** verification where a fix is needed.
