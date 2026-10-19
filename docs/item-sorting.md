# Sorting items

Each list has a **Sort** choice under **Options**. It only changes the order of the rows on screen. The server does not store it, and other people keep their own choice.

| Choice | Order |
| --- | --- |
| Name A–Z | Default. By name, ignoring case. |
| Name Z–A | By name, reversed. |
| Date: soonest first | By date, earliest first. |
| Date: latest first | By date, latest first. |
| Added: newest first | By the last time the item was added, newest first. |
| Added: oldest first | By the last time the item was added, oldest first. |
| Most added first | By how many times the item was added, most first. |
| Fewest added first | By how many times the item was added, fewest first. |

## Rules for every choice

- Open items come first, checked items below. Both groups use the chosen order.
- A row you check or uncheck stays where it is until 1.5 s after your last tap, then slides to its place. Other rows take the free places in the usual order. A new sort or tag filter applies at once.
- Ties are broken by name A–Z, so rows do not jump around.
- **Date** is the optional date on an item. Items with a date come first in both directions. Items without a date come last, by name.
- **Added** counts from the last add. What counts as an add is in the [JSON API](api-lists-items.md#operation-types). An item with no time (added before the counter existed) counts as the oldest.
- **Most added** uses the count that is shown in the item dialog. Adds, re-adds and unchecks count (see [JSON API](api.md)).

## Saved choice

The choice is saved per list, in this browser only, like **Show quantities**. A missing or unknown saved choice means Name A–Z. Clearing the browser's site data resets it.
