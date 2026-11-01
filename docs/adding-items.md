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

When the field is blank, a **Usual items** row offers up to three checked
items from this list that have been added at least twice. It ranks by the
existing per-item, per-list count, then name. Unchecked items are left out
because they are already active on the list. These are separate buttons, not
combobox suggestions: use **Tab** past **Add**, then **Enter** to choose one,
or tap it. Choosing a checked item uses the normal add behavior and restores it.

The row uses the saved item counts while offline. Choosing one queues the same
normal add operation as typing a name; it is sent when the app reconnects. See
[offline use](offline-viewing.md#waiting-changes).

This follows the W3C's [combobox pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/)
for keyboard navigation and its [editable combobox with list autocomplete
example](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-autocomplete-list/).

## Reusable item groups

Open **Options**, then **Item groups**, on a room list to add a saved group or
manage the room's groups.
When creating or editing a group, add one name at a time. Suggestions come from
existing items in every list in the current room; choose a suggestion or add a
new name you typed. The saved group shows its names in order, and each can be
removed before saving. Suggestions do not search other rooms. See
[offline use](offline-viewing.md#what-works-offline) for adding saved groups
without a connection.
