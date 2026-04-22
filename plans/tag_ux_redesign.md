# Tag UX tweaks

## Goal
Define clear behavior for list item rows when Quick Tags are enabled, with a mobile-first layout.

## Item Row Layout (Quick Tags ON)
Each list item row should be split into two groups:

- Left group: (listed from left to right)
  - checkbox
  - small spacing
  - item text (takes remaining available width)
- Right group: (listed from right to left)
  - delete icon button
  - small spacing
  - edit icon button
  - medium spacing
  - tag letter buttons (takes the needed width do display all elelments)

## Spacing Rules
- Small spacing: 4px equivalent
- Medium spacing: 8px equivalent


## Tag Letter Behavior
- Every list tag is shown as its first uppercase letter in the item row.
- If a tag is active on that item:
  - show filled style
- If a tag is inactive on that item:
  - show outlined style

## Row Priority Rules (Mobile)
- Delete and edit buttons should remain visible and tappable.
- If horizontal space is tight:
  - item text truncates with ellipsis
  - action buttons and tag letters remain visible
- Item row should stay on one line (no internal wrap).


## Progress
- [x] Initial UX behavior spec written
- [x] Spec reviewed together
- [x] Implementation started
- [ ] Mobile validation complete
