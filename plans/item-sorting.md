# Item sorting

Lifecycle: tracked

A small sort menu on each list page. Waiting for two other pieces of work (see
[before we start](#before-we-start)); the [backlog](backlog.md) tracks when.

## What the user gets

A "Sort" choice in the list page's menu with these options:

| Sort | Directions |
| --- | --- |
| Name | A–Z (default, today's order) / Z–A |
| Date | Soonest first / Latest first |
| Added | Newest first / Oldest first |
| Most added | Most first / Fewest first |

"Date" is the optional date on an item (the `item-date` prototype). The app
calls it just "Date", not "due date": it can also mean an event day, an expiry
or a planned day.

## Rules for every sort

- Open items on top, checked items below. Both groups use the chosen sort.
- Ties are broken by name A–Z, so the order never jumps around.
- Date: items with a date come first in both directions; items without a date
  go last, by name. "Soonest first" puts overdue items at the top.
- Added: the last time someone added the item. Adding a checked item again
  (the "Restored milk!" case) counts as adding. Undo after delete does not.
  Items from before this change have no time; they count as oldest.
- Most added: how many times the item was added (from the counter work).

## Where the choice is saved

In this browser, per list, like "Show quantities" (`frontend/src/lib/list/items.ts`).
No server change, and changing your sort never changes it for others sharing
the list. Unknown or missing saved values fall back to Name A–Z.

Revisit only if people ask for a shared sort.

## Before we start

1. The `item-date` prototype is finished and in `integration`.
2. The times-added counter is done. It adds a per-item count on the server.
   Add the "last added" time in the same migration, so the sort work needs no
   database change of its own:
   - `add_count`: +1 on add and on re-adding a checked item.
   - `added_at`: set at the same moments; NULL for existing items.
   - Both sent with each item to the frontend and kept in offline data.

If the counter work does not add `added_at`, step 1 below adds it.

## Steps

Each step is small and tested on its own.

1. (Only if needed) Server: `added_at` column, set on add and re-add, sent to
   the frontend. Pytest.
2. Sort logic: extend `sortItems` in `frontend/src/lib/data/order.ts` to take a
   sort key and direction. All options live in one table, so a new sort is one
   entry. Vitest for every rule above.
3. Saved choice: read and write per list in this browser, with the fallback.
   Vitest.
4. Menu: the Sort choice in the list page menu, showing the current sort.
   Browser suite (Chromium, Firefox, WebKit).
5. Docs: describe the sort in the current UX docs; update the backlog.

## Not now

- Filters (for example "only items with a comment"). Hiding items makes people
  think they are missing.
- A shared sort saved on the list.
- Dragging items into a custom order.

## Progress

- [ ] Before we start: `item-date` in `integration`
- [ ] Before we start: times-added counter in `integration`
- [ ] Step 1: `added_at` (skip if the counter work added it)
- [ ] Step 2: sort logic
- [ ] Step 3: saved choice
- [ ] Step 4: menu
- [ ] Step 5: docs and backlog
