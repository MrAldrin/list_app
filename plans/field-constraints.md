# Field constraints

Lifecycle: tracked

Goal: make the database reject bad values, not only the app code. Today most
rules live only in Python. A bug, a script or a future code path could store a
blank name, a quantity of 0 or broken tag data, and the database would accept it.

This is an audit and a proposal. Nothing here is implemented. You choose which
rules to keep.

## Terms in simple words

- **NOT NULL**: the column must have a value. `NULL` means "no value at all",
  which is different from an empty text `''`.
- **CHECK**: a small rule the database tests on every insert and update, for
  example `quantity >= 1`. A write that breaks it fails with an error.
- **Table rebuild**: SQLite cannot add NOT NULL or CHECK to an existing column.
  Instead we create a new table with the rules, copy the rows, drop the old
  table and rename the new one.

## Data audited

- Source: local deploy backup `list-deploy-20260929T202003Z-b7195a87.db`, taken
  2026-09-29. Queried as a copy, with counts only.
- Schema version (`PRAGMA user_version`): 1, so before migration 2.
- Rows: 10 rooms, 21 lists, 287 items, 4 room access tokens, 1 invitation.

## Current state and proposed rules

"App" means validation in `src/database_crud.py` and `src/item_service.py`.
"Bad rows" is the count in the audited copy that would break the proposed rule.

### rooms

| Field | Database today | App today | Bad rows | Proposal |
|---|---|---|---|---|
| `name` | NOT NULL | trimmed, not empty; no length limit (invite form has `maxlength=100`) | 0 (max length 18) | CHECK not empty, trimmed, at most 100 characters |
| `slug` | UNIQUE, nullable | always generated | 0 NULL; 1 legacy slug with capitals and `_` | NOT NULL, not empty. No format check: slugs are in saved links, so keep old ones |
| `password_hash` | NOT NULL | bcrypt hash | 0 empty | Keep as is. Not worth a check |
| `authorization_version` | NOT NULL DEFAULT 1 | increments | 0 below 1 | CHECK `>= 1`. Cheap safety net |

### lists

| Field | Database today | App today | Bad rows | Proposal |
|---|---|---|---|---|
| `name` | NOT NULL | trimmed, not empty; no length limit | 0 (max length 18) | CHECK not empty, trimmed, at most 100 characters |
| `slug` | UNIQUE, nullable | always generated | 0 NULL | NOT NULL, not empty |
| `room_id` | nullable, no foreign key | always set | 0 NULL, 0 orphans | NOT NULL. A foreign key to `rooms` is a separate decision; leave it out |
| `share_token` | unique index, nullable | 43-character token | 0 NULL, 0 wrong length | NOT NULL. Length check not worth it |
| `list_tags` | NOT NULL DEFAULT `'[]'` | written with `json.dumps`; broken JSON read as `[]` | 0 invalid, 0 not an array | CHECK valid JSON array |
| tag text | none | trimmed, not empty; no length limit | 0 blank (max length 6, max 2 tags) | Limit tag length to 30 in the app only. A per-element database check is not worth the complexity |
| `hide_done_*` | NOT NULL + CHECKs | validated | 0 | Keep as is |

### items

| Field | Database today | App today | Bad rows | Proposal |
|---|---|---|---|---|
| `name` | **nullable** | trimmed, lowercase, not empty; no length limit | 0 NULL, 0 blank, 0 not lowercase (max length 53) | NOT NULL; CHECK not empty, trimmed, `name = lower(name)`, at most 100 characters |
| `description` | nullable, DEFAULT `''` | trimmed; no length limit | 0 NULL (max length 191) | NOT NULL DEFAULT `''`; CHECK at most 1000 characters |
| `quantity` | **nullable**, DEFAULT 1, no minimum | kept at 1 or more | 0 NULL, 0 below 1 (max 3) | NOT NULL DEFAULT 1; CHECK `quantity >= 1`. No upper limit: not worth it |
| `done` | **nullable** `BOOLEAN` | 0 or 1 | 0 NULL, 0 other values | NOT NULL DEFAULT 0; CHECK `done IN (0, 1)` |
| `completed_at` | nullable | set on check, cleared on uncheck, UTC ending in `Z` | 0 unchecked items with a time; **207 checked items without a time** | CHECK `done = 1 OR completed_at IS NULL`. Do **not** require a time on checked items (see below) |
| `active_tags` | NOT NULL DEFAULT `'[]'` | written with `json.dumps` | 0 invalid, 0 not an array | CHECK valid JSON array |

The 207 checked items without a time were checked before completion times
existed. The app treats a missing time as "unknown": "hide after N days" keeps
them visible, and "keep recent" sorts them as oldest
([checked-item visibility](../docs/checked-item-visibility.md)). Filling in a
fake time would change what users see, so the rule only covers the safe
direction: an unchecked item has no completion time.

### Not changed

- `room_access_tokens` and `room_invitations`: already strict, 0 problems found.
- The unique name indexes use `trim(name)` and skip blank names. With the new
  checks they could be simpler, but they still work. Leave them.

## Notes on the checks

- SQLite's `lower()` and `trim()` only handle plain ASCII letters and spaces.
  Python's `.lower()` and `.strip()` do more. So the database checks are a
  safety net, and the Python rules stay the main rules. Every value the Python
  code stores already passes these checks.
- `length()` counts characters, not bytes. Emoji and accents count as one.
- Length limits need app validation first, with a friendly message. Otherwise a
  long name would reach the database and show a server error instead.
- JSON checks use `json_valid(x) AND json_type(x) = 'array'`. The app's SQLite
  is 3.50, which includes JSON support.

## Fixing existing bad rows

The audited copy has no rows that break the proposed rules. Production may
change before deploy, so migration 3 should:

- Repair values with an obvious fix: NULL quantity or quantity below 1 becomes 1;
  NULL description becomes `''`; NULL `done` becomes 0; an unchecked item's
  completion time becomes NULL; invalid tags JSON becomes `'[]'`.
- Not guess on names and long text. If a name is blank or too long, the
  migration fails and rolls back. The deploy rehearsal on a fresh backup copy
  catches this before production.

## Proposed migration approach

1. First change: app-side length limits and messages (room, list and item names
   100; description 1000; tag 30). Tests for each limit.
2. Second change: migration 3, `_migration_3_field_constraints`, appended in
   `src/database_setup.py`. It builds on migration 2 and never edits it.
   - Rebuild `rooms`, `lists` and `items` in SQLite's documented order: create
     `<table>_new`, copy with the repairs above, drop the old table, rename the
     new one ([migration notes](../docs/deployment.md#schema-migrations)).
     Foreign keys are off while migrations run, and the runner checks them
     afterwards.
   - Save each table's index SQL before the rebuild and run it again after, as
     migration 2 does.
   - Keep `items` as `AUTOINCREMENT` and **carry over its `sqlite_sequence`
     value**. A plain copy resets the counter to the highest remaining ID, which
     would bring back the item-ID reuse bug that migration 2 fixed.
   - Tests: each rule rejects a bad write; each repair works; an old database
     at version 2 migrates; IDs are not reused after the migration.
3. Deploy only after `item-id-fix` (migration 2), with the
   [deployment checklist](../docs/deployment.md#deployment-checklist). Expect
   `Database migrated from version 2 to 3`.

## Decisions

Agreed with the user on 2026-09-30:

- Keep all proposed rules, including the `authorization_version` check.
- Length limits: 100 for room, list and item names; 1000 for descriptions; 30
  for tags.
- A blank or too-long name stops the migration and rolls it back. No automatic
  shortening.

## Progress

- [x] Audit schema, app validation and production copy (counts only)
- [x] Write proposal
- [x] User chooses rules and limits
- [ ] App-side length limits and tests
- [ ] Migration 3 and tests
- [ ] Update `docs/item-writes.md` and related docs with the new rules
- [ ] Rehearse on a fresh backup copy and deploy
