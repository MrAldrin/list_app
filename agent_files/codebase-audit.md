# ListR Codebase Audit

Items are removed when resolved. Resolved can be fixing it, adding it to backlog, or discarding the idea.

## Scope

I inspected the source code, tests, deployment files, git history, ignored runtime files, and both SQLite databases. This is an assessment only; no implementation changes have been made.

## Overall recommendation

Keep **SQLite** and **NiceGUI** for now.

For two users, and probably for around 20 users, SQLite is a good fit if:

- the app runs as one process/service;
- the database is stored on persistent local volume storage;
- regular backups exist;
- the app is not horizontally scaled across multiple instances.

The immediate problems are data integrity, authentication/session handling, backups, and concurrent updates—not the choice of SQLite or NiceGUI.

## Highest-priority findings

### 1. Existing database migration broke the foreign key

Relevant code: `src/database_setup.py:55-75`

The migration renames `lists` to `lists_old`, creates a replacement `lists` table, and drops `lists_old`. SQLite rewrote the existing `items` foreign key to point at `lists_old`.

The current `list.db` confirms:

```text
items -> lists_old
```

The current database also has foreign-key enforcement disabled:

```text
PRAGMA foreign_keys: 0
```

`PRAGMA integrity_check` reports `ok`, but `PRAGMA foreign_key_check` reports errors for the current item rows. This is because the physical database structure is valid while the relationships are not.

**Recommendation:**

1. Back up `list.db` before changing anything.
2. Create a proper migration that rebuilds `items` with a foreign key to `lists`.
3. Enable foreign-key enforcement.
4. Prefer `ON DELETE CASCADE` or retain carefully tested explicit deletion.
5. Add a migration test using an old database schema.

Do not simply enable foreign keys on the current database before repairing it.


## SQLite assessment

SQLite is suitable for the current application because the data volume and write rate are small. SQLite supports many readers and serializes writes, which is sufficient for a shared shopping list.

The important boundary is not 20 users. Consider PostgreSQL when one or more of these become necessary:

- multiple application processes or Railway replicas;
- sustained high concurrent write volume;
- managed high availability or failover;
- multiple regions;
- complex user accounts, invitations, permissions, and audit history.

For the current design, improve SQLite setup instead:

- use a versioned migration system, for example `PRAGMA user_version`;
- enable `PRAGMA foreign_keys = ON`;
- use WAL mode for better read/write concurrency;
- set a busy timeout;
- use an absolute `DB_PATH` pointing to Railway persistent storage;
- keep the application as one process/service;
- make regular backups and test restoring them;
- eventually replace the single global connection with a small connection/context-manager layer.

Do not store the database in git. Backups should be separate from source control.

## Collaboration correctness issues

### Duplicate items can be created concurrently

`item_service.add_or_restore_item()` first searches for an item and then inserts one. Two users can perform those operations simultaneously and both insert the same item.

There is no database uniqueness constraint for `(list_id, name)`.

**Recommendation:** Add a database-level unique constraint and implement the add/restore operation atomically.

### Quantity updates can overwrite each other

The UI calculates a new quantity from the value captured when the page was rendered. If two users click `+` at the same time, both can write the same result instead of incrementing twice.

**Recommendation:** Use an atomic SQL increment/decrement operation.

### Undo loses item information

`src/main.py:1407-1427` stores only the item's name, done state, and tags. Undoing a deletion loses the description and quantity. The captured item ID is not reused.

**Recommendation:** Store and restore all item fields needed for a faithful undo.

### Failed name updates still change quantity

In the item edit dialog, quantity is updated before the code checks whether the new name is invalid or duplicated. A failed rename can therefore still modify quantity.

**Recommendation:** Validate first, then perform the updates as one operation.

### Updates are not fully atomic

Several service functions perform a read/check followed by a separate write. This is acceptable for light use but can produce stale decisions as more people edit the same list.

Add database constraints and transactions around state-changing operations.

## Realtime update performance

`broadcast_updates()` calls global NiceGUI refreshable functions. This means an item change can rerender every active item list, including unrelated lists and users.

This is fine for the current small database, but becomes wasteful with more users or lists.

**Recommendation:** Later, introduce targeted updates by list/room or a subscription model. This is not a reason to leave NiceGUI yet.

## Deployment and runtime issues

### Production reload is enabled

`src/main.py:1525-1534` calls `ui.run(..., reload=True)`.

Auto-reload is useful during development but should be disabled in production. It can cause unnecessary restarts and complicate long-lived WebSocket connections.

### Database path is implicit

There is no `DB_PATH` in the current `.env`, so the app uses the relative path `list.db`. This depends on the working directory and may accidentally write to ephemeral deployment storage.

**Recommendation:** Set an explicit absolute path for the Railway volume and verify persistence after restart.

### Runtime dependency classification

`python-dotenv` is imported by runtime code but declared only in the development dependency group. It currently arrives transitively through NiceGUI, but relying on that is fragile.

**Recommendation:** Declare it as a runtime dependency or make dotenv loading development-only.

### Flat module imports are fragile

The application relies on running `src/main.py` directly and importing modules such as `database_crud` as top-level modules. The tests manually add `src` to `sys.path`.

This works, but importing the app as `src.main:app` or packaging it normally would be fragile.

**Recommendation:** Gradually move toward a real package, such as `src/list_app/`, when modularizing. This is not urgent for the MVP.

## Data model observations

### JSON tags are acceptable for now

`list_tags` and `active_tags` are stored as JSON text. For a small shopping list this is simple and adequate. There is no need to introduce PostgreSQL or normalize tags immediately.

Consider separate tag tables later if tags need searching, reporting, sharing, or stronger constraints.

### Schema constraints are weak

Several fields that should be required are nullable, and `quantity` has no database check constraint. Examples include:

- nullable item names;
- nullable item completion state;
- nullable room/list slugs;
- quantities below one being possible through low-level CRUD;
- unrestricted text lengths;
- arbitrary JSON tag values.

**Recommendation:** Add `NOT NULL`, `CHECK`, and sensible length constraints as part of a deliberate migration.

### No timestamps or change versions

There are no `created_at`, `updated_at`, or change-version fields. These would help with debugging, audit history, and conflict detection.

They are not required for the MVP, but become useful as collaboration grows.

### Shared room passwords do not provide user identity

The current model gives every room member the same permissions and password. That is reasonable for a couple, but with 20 users it cannot provide individual revocation or audit trails.

Add accounts/invitations only if those features are actually needed. That would be a product/security change, not merely a database change.

## PWA observations

`src/static/sw.js` registers a service worker but does not populate its cache. Its offline fallback therefore provides no meaningful offline behavior.

**Recommendation:** Either remove the service worker until offline support is designed, or implement a real cache and synchronization strategy. A realtime NiceGUI application cannot automatically become offline-capable just by registering a service worker.

The viewport configuration disables user zooming with `user-scalable=no`. This is an accessibility problem. The 16px input styling should be sufficient to prevent iOS input auto-zoom without disabling pinch zoom.

## Maintainability observations

`src/main.py` is approximately 1,532 lines and contains routes, authentication, dialogs, rendering, state management, and PWA setup.

NiceGUI is still a suitable technology, but this file should eventually be split into modules such as:

- configuration/authentication;
- admin page;
- room page;
- list page;
- reusable item/tag/dialog components;
- PWA/static setup.

Some writes use `item_service.py`, while others call `database_crud.py` directly from UI callbacks. A consistent service layer would make validation, authorization, and transactions easier to enforce.

## Testing and documentation gaps

Current checks:

- Ruff formatting: passing;
- Ruff lint: passing;
- pytest: 47 tests passing;
- `ty check`: one error involving `lastrowid` possibly being `None`;
- pytest emits a Starlette/httpx deprecation warning.

Missing high-value tests include:

- migrations from each old schema;
- foreign-key integrity;
- malformed password hashes;
- password-change session invalidation;
- public-list access boundaries;
- concurrent duplicate item creation;
- atomic quantity updates;
- tags;
- room creation/deletion;
- undo preserving descriptions and quantities.

The README is empty. There is no `.env.example`, deployment guide, backup guide, or recovery guide.

The `.gitignore` rule `.*/` is broad and would ignore future directories such as `.github/`, making CI configuration inconvenient to add.

## Suggested order of work

### Before relying on the app more heavily

1. Back up and repair the broken SQLite foreign key migration.
2. Remove or repair the invalid test room.
3. Rotate the three-character admin password.
4. Remove the known `dev_password` fallback.
5. Set an explicit absolute database path on persistent storage.
6. Disable production reload.

### Next small implementation steps

1. Add versioned migrations, foreign keys, WAL, and busy timeout.
2. Add database uniqueness and atomic item add/restore behavior.
3. Fix quantity update ordering and undo data loss.
4. Replace raw room passwords in local storage with opaque authorization tokens.
5. Add migration, authentication, and concurrency tests.
6. Add a README, `.env.example`, backup instructions, and CI.
7. Split `main.py` gradually.

### Defer until there is a real need

- migrating to PostgreSQL;
- adding SQLAlchemy or Alembic;
- replacing NiceGUI with React or another frontend;
- implementing full user accounts;
- normalizing tags into separate tables.

The immediate gains are available without changing the main technology stack.
