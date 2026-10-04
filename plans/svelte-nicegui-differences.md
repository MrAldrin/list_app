# Svelte vs NiceGUI differences

Lifecycle: temporary

User-visible ways the Svelte prototype (`/app/`) differs from the NiceGUI app.
We go through the list one row at a time. For each row, the owner chooses
**match** NiceGUI, **keep** Svelte, or **later**. Rows already covered by the
[decisions log](svelte-frontend-rewrite.md#decisions-log) or a Milestone 3
step count as recorded. We only reopen them if the owner wants to.

## Unrecorded (decide these)

| # | Area | NiceGUI | Svelte | Choice |
|---|------|---------|--------|--------|
| U1 | List page: scrolling | Header, tags and add field stay fixed; only the items scroll | The whole page scrolls | Match, partly: top bar and add field stay; done (`rmsxykwl`) |
| U2 | Long names (lists, list title, items) | One line, cut off with "…" | Wrap onto more lines | Match: rows need the room for tags and delete; done (`zstuwvqn`) |
| U3 | Start page: errors | Toast at the top | Red text under the field | Keep: the error stays next to its field |
| U4 | Start page: position | Card centered on the screen | Card near the top | Keep: stays above the phone keyboard |
| U5 | Toast position | Top of the screen | Bottom, full width, above the keyboard | Keep: Undo near the thumb; does not cover the sticky bar |
| U6 | Item checkbox | Quasar checkbox | The browser's own checkbox, larger tap area | Keep; rows now 36 px, tags 26 px (`wryqrwqy`, update decision 90) |
| U7 | Options: "Show quantities", "Only show minimum 2" | Sliding switches | Checkboxes | Match: sliding switches; done (`mmzvvxny`) |
| U8 | Quantity stepper on rows | Tiny −/+ in a grey box | Larger −/+ buttons (44 px tap areas) | Match look: grey box, compact, same-width digits; done (`wonkqmrs`) |
| U9 | Text fields ("Add or Search", "Add Tag") | Label sits in the field and moves up when typing | Grey hint text that disappears when typing | Keep: saves space in the sticky field |
| U10 | List gone page | Centered icon, text, "Back to room" button | Card with text and a "Back to room" link | Keep the card; centered button and text, as NiceGUI; "This list was deleted." when it vanishes while open, else "List not found. It may have been deleted." (update decision 82); done (`nwyvlnxz`) |

## Recorded (decided before, skip unless the owner wants to)

| # | Area | NiceGUI | Svelte | Covered by |
|---|------|---------|--------|------------|
| R1 | Room header | ⋮ menu: share, add to home screen, rename, change password, delete | "Log out" button only | Decision 74; steps 3.1, 3.2, 3.5 |
| R2 | List header | ⋮ menu: share, reset share link | No menu | Step 3.2 |
| R3 | Start page | "Admin" button | None | Step 3.3 |
| R4 | Start page: unknown room | "Room not found" toast | Opens the password prompt | Step 3.1 |
| R5 | Dark mode | Moon button at the top right, saved per device | Follows the phone setting, no button | Step 3.6 (theme) |
| R6 | Password prompt | Shows the room name; "Incorrect password" | No room name; "Wrong room or password." | Decision 73 |
| R7 | Load errors | "Could not verify room access. Please retry." | "Could not load this room." + Retry | Decision 93 |
| R8 | Undo after delete | Undo bar in Options mode | "Undo" in the toast | Decisions 85, 87 |
| R9 | Hide mode | Quasar toggle buttons | Segmented control | Decision 89 |
| R10 | − at quantity 1 | Sends a write that changes nothing | Disabled | Decision 84 |
| R11 | Tag colors and buttons | Quasar colors | Darker shades, 32 px circles | Decision 90 |
| R12 | Connection status | None | "Reconnecting…" pill after 800 ms | Decision 91 |
| R13 | Existing list name | "List created" toast | No toast (later "Opened existing list") | Decision 78; step 3.6 |
| R14 | List gone text | "This list was deleted." | "…deleted or is not in this room." | Decision 82 |
| R15 | Deleted tag filter | Keeps filtering | Stops filtering | Decision 88 |

## Progress

- [x] List the differences
- [x] Ask the owner for other differences they noticed (none besides U1)
- [ ] Decide U1–U10 with the owner
- [ ] Do small fixes (one jj change each); put bigger ones into Milestone 3
- [ ] Move decisions into the Svelte plan; remove the backlog Next item; delete this plan
- [ ] Resume the Gate A checklist at Tags
