# Due-date reminders

The due bell shows the items that are due, in the room or on the list on
screen. It needs no permission and no setup, and works from saved data when
offline. Nothing interrupts editing: there are no reminder toasts. The bell's count
and the list counts are the due signals; date labels mark each dated item.
Phone notifications are not built yet
(see the [plan](../plans/due-date-reminders.md)).

## Shared due time

An item can also have a time and an explicit IANA time zone. Clearing its date
clears both. The server confirms the UTC instant; an unsynced change shows
**Waiting to sync** instead. These shared edits use the existing offline queue.
Confirmed timed items become overdue after their confirmed instant. Other timed
items are grouped by that instant in the browser time zone. Until device settings
are available, the browser time zone is used for day groups. Unconfirmed edits
use their wall date and never invent a UTC instant.

## What counts as due

An item is due when it is not checked and has a date. "Today" and "Tomorrow"
are days in the browser time zone. Items without a date never show as due.

| Group | Days from today |
| --- | --- |
| Overdue | date-only before today; timed after the confirmed instant |
| Today | today |
| Tomorrow | tomorrow |
| Next 7 days | days 2–7 |
| Later | after day 7 |

## The bell

- **Room page and list page** have a bell. The room page's bell lists every
  dated, unchecked item in the room, with its list name. The list page's bell
  starts on that list; a room user can switch to the whole room. A share link
  shows only its list, never the room.
- The badge counts unchecked items that are overdue, due today or due tomorrow.
  Zero shows no badge; above 99 it shows `99+`. Overdue items make the badge red.
  Opening the panel does not clear it.
- The panel groups items as in the table. Empty groups are hidden. Items are
  sorted by day, then by list name, then by item name.
- Tapping an item opens its list with the item revealed: the tag filter and
  the search text are cleared, and the item is focused. A short status says
  which filter was cleared; nothing is cleared, and no status shows, when
  neither was set.
- If the item is no longer on that list, the page says so.
- The panel is marked "Saved data" when the page cannot confirm the latest data.
- Updates from other devices change the panel's content without moving focus.

## List cards

Each list on the room page shows its due count, such as "2 due, 1 overdue".
The count uses the same rule as the bell badge, for that list only.

## Date labels

An item's date shows its label beside the date: **Overdue** in red, **Today**
and **Tomorrow** in amber. Later dates have no label. The words carry the
meaning; the color repeats it. Colors come from the theme tokens, which meet
contrast in every theme and light/dark mode ([app colors test](../frontend/src/app-colors.test.ts)).

## Day changes

The views recompute every minute and when the page is shown again. Timed
deadlines, day changes, labels and counts update without a reload.

## Code

- Rules: `frontend/src/lib/list/due-reminders.ts` (tests next to it).
- Day clock: `frontend/src/lib/list/due-clock.svelte.ts`.
- Bell and panel: `frontend/src/lib/list/DueCenter.svelte`, placed in
  `RoomHeader.svelte` and, through `ListHeader`'s bell slot, in `ListView.svelte`.
- Reveal link and read: `frontend/src/lib/list/reveal.ts`, used by `ListView.svelte`.
- Browser tests: `browser_tests/test_svelte_due_center.py`.
