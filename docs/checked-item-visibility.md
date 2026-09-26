# Hiding checked-off items

Each list has its own shared visibility setting under **Options**. The setting hides rows on screen; it does **not** delete items. Unchecked items always appear, and hidden items still match Add/Search suggestions. Adding a hidden checked item again unchecks and reveals that same item. To see every item, turn **Hide checked-off items** off.

- **Hide checked-off items** starts off. Turn it on to hide every checked item immediately.
- With hiding on, choose at most one optional mode:
  - **Only after X days** shows checked items until X full 24-hour periods have passed since each was checked; default X is **7**.
  - **Keep last X checked items** shows the X most recently checked items, regardless of age; default X is **10**. This counts across the entire list, even when a tag filter is active.
- Both counters take whole numbers from 0 through 100,000. **0** hides all checked items. Turning off the main switch retains the counter values; turning it back on selects hide-all (neither optional mode), not the last selected mode.

The server stores completion times in UTC. Unchecking an item clears its completion time; checking it again starts a new period. Repeating the same checked state does not restart the clock. Open age-filtered pages update within about a minute of an item passing the threshold; edits and setting changes also update connected list viewers immediately. A page refresh is not needed to save settings.

## Existing lists and verification

Items already checked before this feature have no known completion time. They hide in immediate mode; in day mode they remain visible until unchecked and checked again (except when X is 0). In last-X mode, known check-off times rank first; older items without times are approximated by newest item creation ID, not an invented check-off date. Deleting and undoing an item preserves its check-off time.

**Locally verified:** SQLite migration and idempotency tests, completion/visibility rules, list-identity writes, UI tests, and Chromium/Firefox shared-list browser tests. A production database migration and real-device behavior have **not** been verified; use the [deployment checklist](deployment.md) and the [outstanding checks](../plans/backlog.md#deployment-and-recovery--next-priorities) before treating those as complete.
