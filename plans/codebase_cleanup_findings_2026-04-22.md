# Codebase Cleanup Findings (2026-04-22)

## Scope
Reviewed:
- `src/main.py`
- `src/database_setup.py`
- `src/database_crud.py`
- `src/item_service.py`
- `tests/test_database_crud.py`

## Current status
- Test suite: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q` -> **42 passed**
- Lint: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` -> **all checks passed**

## Findings (ordered by severity)

### 1) High (completed): Shared global SQLite cursor is unsafe under concurrent requests
- Status: **Done**
- Original evidence (before cleanup):
  - `src/database_setup.py:8` creates a single global `cursor`.
  - `src/database_setup.py:50` exports `db, cursor` as module globals.
  - `src/database_crud.py:2` imports and reuses that one cursor for all queries.
- Why this matters:
  - The architecture expects multiple users at once. A shared cursor can produce intermittent runtime errors under overlap (for example: cursor re-entrancy issues) and is not a good concurrency boundary.
- Recommendation:
  - Keep one shared connection if needed, but create short-lived cursors per operation (`db.execute(...)` or `db.cursor()` inside each function).
  - Add a small concurrency test (or stress test script) for overlapping writes.
- Completed changes:
  - Removed global shared cursor usage.
  - Updated CRUD operations to use the shared connection directly.
  - Added a lightweight DB lock (`threading.RLock`) around CRUD operations to prevent concurrent connection misuse in this MVP architecture.
  - Updated test setup to stop importing/using a shared cursor.

### 2) Medium (completed): Unused imports in `src/main.py`
- Status: **Done**
- Completed changes:
  - Removed unused import `context`.
  - Removed unused imports `STATUS_DELETED` and `STATUS_RENAMED`.

### 3) Low (completed): Test lint quality issues
- Status: **Done**
- Completed changes:
  - Renamed ambiguous loop variables (`l` -> `entry`) in `tests/test_database_crud.py`.
  - Removed unused variable assignment (`list_id2`).

## Architecture alignment check
No major architecture drift found relative to `ARCHITECTURE.md` core decisions (NiceGUI + SQLite + modular layers).

The previously identified shared-cursor risk has been addressed.

## What is left to clean up
No open cleanup items from this findings file.

## Progress tracking
- [x] Review app modules and tests
- [x] Run tests and lint
- [x] Document findings in `plans/`
- [x] Implement low-risk cleanup (unused imports + test lint fixes)
- [x] Implement shared-cursor concurrency cleanup
- [x] Add concurrency-focused regression test(s)
