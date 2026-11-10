# ListR theme gallery (prototype)

A static, local-only design exploration. It is not part of the app, its build,
its routes, its data, or its service worker. Nothing here is an accepted
product design.

## Open it

Serve this folder as static files on loopback only, for example at
`http://127.0.0.1:8766/`, and open `preview.html`
(`http://127.0.0.1:8766/preview.html`). `index.html` redirects there.

No server code, no build step, no dependencies. Files:

- `preview.html`: page shell and edit/add-list dialogs.
- `gallery.css`: all styling, including the reference and all 20 drafts.
- `gallery.js`: synthetic sample data, the 20 drafts, and mock interactions.

## Scope

- Reference: the current app's room and list layout, copied as static markup
  and CSS from `frontend/src/lib/room`, `frontend/src/lib/list` and
  `frontend/src/lib/ui` (read only). No live app code or data is used.
- 20 drafts in four freedom levels (5 each), plus the reference outside the count.
- Sample data: four synthetic lists with long and short names, checked and
  unchecked items, quantities, tags, and due dates. Reloading resets it.

## Mock interactions (local only)

Working: add an item (Enter or the button), check/uncheck, open and edit an item
(Save, Cancel, quantity, tags, date), tag filter, tag toggle on the reference,
add a list (dialog only, stored in memory).

Illustrative only (shown, labeled, and disabled or non-functional): room
switcher, due center, room and list menus, Options panel, list rename and delete
in the reference, personal reminders, sharing, and tag rename/color.

No requests leave the page. No storage, cookies, or preferences are written.

## Seams and assumptions

Each draft card names its implementation seam (palette-only, component styling,
layout, or interaction). Level 3 and 4 layouts add prototype-only assumptions
such as a persistent list index, display-only tag or date grouping, and
checked/open columns. They are not product decisions.

## Known limits

- The static reference covers the main room/list layout, not every app state.
  Its scenario has quantity controls off and “Only show tags the item has” on.
  These are existing app display settings, not new product rules. The Options
  panel and other labeled illustrative controls cannot change this scenario.
- Main reference icons use the app's inline SVG paths. The room-switch arrow
  remains a text glyph. The local mock edit dialog is not an exact app-dialog
  reproduction. Search suggestions and live status are outside this preview.
- The prototype uses container queries so a phone-width preview keeps its
  narrow layout even in a desktop browser. These checks are not a production
  accessibility or browser-compatibility audit. Check evidence is kept in the
  repository at `docs/background/theme-exploration-review.md`, outside the
  served gallery directory.
- Focus is restored after re-render within the same preview. If its original
  control no longer exists, it falls back to that preview's add field.

## Credits and licenses

- Fonts: system font stacks only. No remote fonts.
- Main reference icons: existing Material Design SVG paths from
  `frontend/src/lib/ui/Icon.svelte` in this repository. Material icons are
  licensed under [Apache 2.0](https://github.com/google/material-design-icons/blob/master/LICENSE).
  Other experimental symbols are Unicode glyphs or original CSS shapes.
- Images: none.
- Reference markup and copy: derived from the ListR frontend (this repository).
- Sample names and notes are invented for the prototype.
