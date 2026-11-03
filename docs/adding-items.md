# Adding items

Use **Add or Search** to type an item or find a name already in the list. The
suggestions are a listbox; arrow keys highlight an option while focus stays in
the field.

- With no suggestion highlighted, press **Enter** or **Add** to add the text you
  typed, even if there are matching suggestions.
- Use **Up** or **Down** to highlight a suggestion, then press **Enter** or
  **Add** to add or restore that item.
- Click or tap a suggestion to add or restore it.
- **Tab** leaves the field and follows the page's normal focus order. It does
  not select a suggestion. **Escape** closes the suggestions; typing again opens
  them.

When the field is blank and focused, the same pop-up list shows **Usual
items** instead: up to three checked items from this list that have been added
at least twice. It ranks by the existing per-item, per-list count, then name.
Unchecked items are left out because they are already active on the list. The
usual items follow the same keyboard and touch rules as suggestions above, and
choosing a checked item restores it. Typing replaces them with the normal
suggestions. Nothing shows under the field until it is focused, so the list
keeps its space.

The usual items use the saved item counts while offline. Choosing one queues the same
normal add operation as typing a name; it is sent when the app reconnects. See
[offline use](offline-viewing.md#waiting-changes).

This follows the W3C's [combobox pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/)
for keyboard navigation and its [editable combobox with list autocomplete
example](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-autocomplete-list/).
