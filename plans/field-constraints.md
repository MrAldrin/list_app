# Field constraints

Lifecycle: tracked

Goal: make the database reject bad values, not only the app code. Today most
rules live only in Python. A bug, a script or a future code path could store a
blank name, a quantity of 0 or broken tag data, and the database would accept it.

The rules are agreed (see Decisions). Progress is at the bottom.

## Terms in simple words

- **NOT NULL**: the column must have a value. `NULL` means "no value at all",
  which is different from an empty text `''`.
- **CHECK**: a small rule the database tests on every insert and update, for
  example `quantity >= 1`. A write that breaks it fails with an error.
- **Table rebuild**: SQLite cannot add NOT NULL or CHECK to an existing column.
  Instead you create a new table with the rules, copy the rows, drop the old
  table and rename the new one. We do **not** do this; see below.
- **Guard trigger**: a `BEFORE INSERT` or `BEFORE UPDATE` trigger that stops a
  bad write with `RAISE(ABORT, ...)`. It gives the same protection as a CHECK
  and can be added to an existing table.

## Data audited

- Source: local deploy backup `list-deploy-20260929T202003Z-b7195a87.db`, taken
  2026-09-29. Queried as a copy, with counts only.
- Schema version (`PRAGMA user_version`): 1, so before migration 2.
- Rows: 10 rooms, 21 lists, 287 items, 4 room access tokens, 1 invitation.
- Re-run on 2026-10-14 with the deploy backup
  `list-deploy-20261013T182609Z-1626e4d0.db` (schema version 5): 11 rooms,
  23 lists, 340 items, and **0 rows break any rule below**.

## Current state and proposed rules

"App" means validation in `src/database_crud.py` and `src/item_service.py`,
as audited. The Svelte app now writes through the JSON API in `src/api/`;
check that path too when adding limits.
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
| `hide_done_*` | NOT NULL + CHECKs; counters 1 or more via migration 5 triggers | validated | 0 | Keep as is |

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
- Offline-sync columns and tables from migration 3 (`uid`, `changed_seq`,
  `change_seq`, `deletions`, `processed_ops`): keep as they are.
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

## Existing rows

Both audits found no rows that break the rules, so migration 6 repairs
nothing. It counts the rows that break each rule first. If any do, it stops
with those counts and rolls back, and the app does not start. The deploy
rehearsal on a fresh backup copy catches this before production.

## Migration approach

Production is at schema version 5 (`_migrations` in `src/database_setup.py`).

**Guard triggers, not table rebuilds.** A rebuild of `rooms`, `lists` and
`items` would have to keep the offline-sync columns and indexes, recreate the
change-tracking and visibility triggers, and carry over the item ID counter. A
mistake there could break syncing or bring back item-ID reuse. Guard triggers
give the same protection without touching the tables. Migration 5 already
guards the hide-done counters this way.

1. First change: app-side length limits with friendly messages (room, list and
   item names 100; description 1000; list tag 30), in the JSON API ops and the
   admin room form, plus `maxlength` on the Svelte inputs. Tests for each limit.
2. Second change: migration 6, `_migration_6_field_constraints`, appended in
   `src/database_setup.py`.
   - Each rule is one SQL condition, written once and used both by the
     existing-row check and by the triggers.
   - Per table, one `BEFORE INSERT` trigger and one `BEFORE UPDATE OF <checked
     columns>` trigger. Updates that only touch other columns (such as the
     change-tracking `changed_seq`) skip the check.
   - Tests: each rule rejects a bad write; normal app writes still pass; a
     database with a bad row stops the migration and is left unchanged.
3. Deploy with the
   [deployment checklist](../docs/deployment.md#deployment-checklist). Expect
   `Database migrated from version 5 to 6`.

## Decisions

Agreed with the user on 2026-09-30:

- Keep all proposed rules, including the `authorization_version` check.
- Length limits: 100 for room, list and item names; 1000 for descriptions; 30
  for tags.
- A blank or too-long name stops the migration and rolls it back. No automatic
  shortening.

Agreed on 2026-10-14:

- Use guard triggers instead of table rebuilds.
- No repairs in the migration: the data is clean, so any bad row stops it.

## Progress

- [x] Audit schema, app validation and production copy (counts only), 2026-09-29 at version 1
- [x] Write proposal
- [x] User chooses rules and limits
- [x] Update the plan for the live schema (version 5), 2026-10-13
- [x] Re-run the data audit on a fresh backup, 2026-10-14
- [x] Switch to guard triggers, 2026-10-14
- [ ] App-side length limits and tests
- [ ] Migration 6 and tests
- [ ] Update `docs/item-writes.md` and related docs with the new rules
- [ ] Rehearse on a fresh backup copy and deploy
