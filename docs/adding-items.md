# Adding items

Use **Add or Search** in the bottom bar to type an item or find a name already
in the list. The field shows up to ten matches above it, with the most-added
match first. Scroll to see more. Each match shows its add count. Arrow keys
highlight a match without moving focus from the field.

- With no suggestion highlighted, press **Enter** or select **Add** to add the
  text you typed, even if matching suggestions appear.
- Press **Up** or **Down** to highlight a suggestion. Then press **Enter** or
  **Add** to add or restore that item.
- Click or tap a suggestion to add or restore it.
- Press **Tab** to leave the field and follow the page's normal focus order.
  Tab does not select a suggestion. Press **Escape** to close the suggestions.
  Type again to reopen them.

When the field is blank and focused, the pop-up shows **Usual items** instead.
These are checked items from this list that have been added at least twice.
Scroll to see more. The list ranks items by the existing per-item, per-list
count, then by name. It leaves out unchecked items because they are already
active on the list. Usual items follow the same keyboard and touch rules as
suggestions. Choosing a checked item restores it. Typing replaces them with
normal suggestions. Nothing appears below the field until you focus it, so the
list keeps its space.

Usual items use saved item counts while offline. Choosing one queues the same
normal add operation as typing a name. The app sends it when it reconnects. See
[offline use](offline-viewing.md#waiting-changes).

This follows the W3C's [combobox pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/)
for keyboard navigation. It also follows the W3C's [editable combobox with list
autocomplete example](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-autocomplete-list/).
