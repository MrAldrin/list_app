# Due-date reminders

The app warns about items whose date is close, with a toast. It works only
while the app is open; there are no phone notifications yet (see the
[backlog](../plans/backlog.md#later)).

## What counts as due

An item is due soon when it is not checked and its date is today, tomorrow or
already past. "Today" is the device's own day. Items without a date never
remind.

## When a reminder shows

| Moment | What it shows |
| --- | --- |
| A list opens | All due items of that list, every time it opens: "3 items due: 1 overdue, 2 today". |
| On load, then every 5 minutes, on any room or list page | Due items in any list that this page has not reminded about yet, named by list: "Due soon: Groceries (1), Chores (2)". |

- A reminder is red when something is overdue, otherwise amber. It stays 8 seconds.
- The same item reminds again after the page is reloaded, or when its date changes.
- A share link sees only its own list.
- Browsers pause timers in background tabs, so the 5-minute check may wait
  until the app is back on screen.

## Code

- Rules: `frontend/src/lib/list/due-reminders.ts` (tests next to it).
- Toasts and the timer: `frontend/src/lib/ui/due-reminder-toasts.svelte.ts`,
  started by `PageShell.svelte`.
