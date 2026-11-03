# Sorting items

Each list has a **Sort** row under **Options**: choose what to sort by, then tap the direction button to reverse the order. They only change the order of the rows on screen. The server does not store them, and other people keep their own choice.

| Sort by | Order (default first) | Sorts by |
| --- | --- | --- |
| Name | A–Z (app default), Z–A | The name, ignoring case. |
| Date | Soonest first, Latest first | The item's optional date. |
| Added | Newest first, Oldest first | The last time the item was added. |
| Most added | Most first, Fewest first | How many times the item was added. |

Picking a new **Sort** starts it in its default order. The pairs live in `ITEM_SORTS` (`frontend/src/lib/data/order.ts`).

## Rules for every choice

- Open items come first, checked items below. Both groups use the chosen order.
- A row you check or uncheck stays where it is until 1.5 s after your last tap, then slides to its place. Other rows take the free places in the usual order. A new sort or tag filter applies at once.
- Ties are broken by name A–Z, so rows do not jump around.
- **Date** is the optional date on an item. Items with a date come first in both directions. Items without a date come last, by name.
- **Added** counts from the last add. What counts as an add is in the [JSON API](api-lists-items.md#operation-types). An item with no time (added before the counter existed) counts as the oldest.
- **Most added** uses the count that is shown in the item dialog. Adds, re-adds and unchecks count (see [JSON API](api.md)).

## Saved choice

The choice (one key with its order) is saved per list, in this browser only, like **Show quantities**. A missing or unknown saved choice means Name A–Z. Clearing the browser's site data resets it.
