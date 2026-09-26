# Hide checked-off items

## Goal and decisions

Reduce clutter without deleting list items. Hidden items remain part of the list and are still matched by Add/Search. This changes visibility, not storage or permissions, and stays within the NiceGUI + SQLite architecture.

- Per-list **Hide checked-off items** starts off. When on with no sub-option selected, hide every checked item.
- When hiding is on, show two mutually exclusive, optional sub-options:
  - **Only after X days**: hide checked items once X full 24-hour periods have elapsed since they were checked. X defaults to 7.
  - **Keep last X checked items**: show the X most recently checked items, regardless of age. X defaults to 10.
- Both counters accept non-negative whole numbers; 0 hides every checked item. Switching one sub-option on turns the other off. Turning the main switch off reveals everything without deleting its chosen settings.
- Unchecked items always remain visible. Tag filtering still applies to the visible items. Options remains available even when no rows are visible. No separate reveal control; turn hiding off to see everything.
- Shared and private list viewers see the same persisted list setting. Both may edit it under the existing list-identity/authorization rules; settings edits broadcast updates to other viewers.

## Data and edge cases

- Persist one visibility mode on `lists` (`off`, `all`, `age`, `recent`), plus day and recent-item counts. Default: `off`, 7, 10. Validate mode and non-negative integer bounds in the write helper; a large reasonable ceiling may be set to keep controls practical.
- Persist a UTC completion timestamp on `items`. Set only when an item transitions from unchecked to checked; clear on uncheck or Add/Search restoration. Repeat writes to the same done state must not reset elapsed time. Use UTC consistently, with a deterministic clock argument/helper for boundary tests.
- Existing checked items have unknown completion time (NULL): `all` hides them; `age` keeps them visible until they are unchecked and checked again; `recent` ranks known completion times first and uses descending item creation ID as a documented approximation for pre-migration items, showing at most X checked rows. Avoid silently assigning a fictitious date.
- For equal timestamps, use descending item ID as deterministic tie-breaker. The recent count is across the entire list, before tag filtering.
- Undo of a deleted item preserves its completion time as well as its existing item fields. Schema repair/rebuild paths must preserve the new columns. Old databases migrate without losing data and repeated initialization is safe.
- Hidden items remain in `get_list_data` and its Add/Search history. Rendering applies visibility on top of that full result; add/restore and duplicate checks continue to operate on all items.
- For age mode, refresh visible lists periodically (e.g. each minute while the page is open) so an item crosses the full-24-hour threshold without an edit. Normal broadcasts refresh immediately after writes. Do not depend on browser timezone or midnight.
- Existing stale item-ID reuse risk remains independently tracked in `plans/backlog.md`; do not claim this feature fixes it.

## Implementation slices

1. **Database and rules.** Add SQLite columns/migrations and reads, atomic identity-checked list visibility setter, transition-aware completion timestamp writes, undo preservation, and a small pure visibility helper. Tests: fresh/legacy/reinitialized schema, transaction failure and stale list identity, exact age boundaries, recent order/ties/legacy items, toggle/re-add/undo, and full-history matching.
2. **NiceGUI wiring.** Put main switch and mutually exclusive sub-options/counters in the existing Options panel, persist via the helper, broadcast, filter only the displayed rows, and add a lightweight periodic refresh for age boundaries. Tests: option state/validation, private and public view, all modes, changing controls and restoring a hidden item, and shared updates. Include browser tests where useful.
3. **References and verification.** Update current behavior in `docs/` and link from `README.md` only if needed. Record unfinished deployment/device checks in `plans/backlog.md` rather than asserting them verified. Run `uv run ruff format .`, `uv run ruff check --fix .`, `uv run pytest -q`, then `uv run ruff format --check .` and `uv run ruff check .`; run relevant browser tests if the local browser setup permits. Independently review the diff and address confirmed defects before handing it back. Do not move `main`, merge, push, or deploy.

## Progress

- [x] Requirements agreed: main switch off; sub-options optional and mutually exclusive; 24-hour days; defaults 7 days/10 items; no separate reveal control.
- [ ] Slice 1 implemented and verified.
- [ ] Slice 2 implemented and verified.
- [ ] Slice 3 references, full checks, and independent review completed.
- [ ] Production/device verification (if needed; track separately when implementation is done).
