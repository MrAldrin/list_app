# Hiding checked-off items

Each list has its own shared visibility setting under **Options**. The setting
hides rows on screen; it does **not** delete items. Unchecked items always
appear. Hidden items still match Add/Search suggestions. Adding a hidden checked
item again unchecks and reveals that same item. Turn **Hide checked-off items**
off to see every item.

- **Hide checked-off items** starts off. Turn it on to hide every checked item immediately.
- With hiding on, the options appear as rows under the **Hide checked-off
  items** switch. A single-choice toggle selects one mode:
  - **All** (default) hides every checked item.
  - **After X days** shows checked items until X full 24-hour periods have passed since each was checked; default X is **7**.
  - **Keep last X** shows the X most recently checked items, regardless of age; default X is **10**. This counts across the entire list, even when a tag filter is active.
- Both counters accept whole numbers from 1 through 100,000. Use **All** to hide
  every checked item immediately. Turning off the main switch retains the
  counter values. Turning it back on selects **All**, not the last selected
  mode.

A muted line under the list counts hidden checked items, for example "5 checked
items hidden". It is plain text and has no action. It appears only when items
are hidden. Search and the tag filter do not change the count.

The browser applies these rules to the items it has loaded, so hiding works offline. The server only validates and stores the settings.

The server stores completion times in UTC. Unchecking an item clears its
completion time. Checking it again starts a new period. Repeating the same
checked state does not restart the clock. Open age-filtered pages update within
about a minute after an item passes the threshold. Edits and setting changes
also update connected list viewers immediately. You do not need to refresh the
page to save settings.

## Existing lists and verification

Existing zero counters reset to the defaults (7 days / 10 items). A list using
zero in its active mode switches to **All**, preserving which items are hidden.

Items checked before this feature have no known completion time. They hide in
immediate mode. In day mode, they remain visible until they are unchecked and
checked again. In last-X mode, known check-off times rank first. The app
approximates older items without times by their newest item creation ID, not by
an invented check-off date. Deleting and undoing an item preserves its check-off
time.
